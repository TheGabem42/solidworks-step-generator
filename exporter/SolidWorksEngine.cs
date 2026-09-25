using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

// Strongly typed COM calls also work on Windows ARM, where PowerShell's
// IDispatch/type-library lookup can fail with TYPE_E_ELEMENTNOTFOUND.
public sealed class StepSession : IDisposable
{
    private ISldWorks app;
    private bool ownsApp;
    private int oldAP, oldGeometry;
    private bool oldAtomic;
    private bool preferencesCaptured;
    public string Revision { get { return app.RevisionNumber(); } }

    public StepSession()
    {
        try { app = (ISldWorks)Marshal.GetActiveObject("SldWorks.Application"); }
        catch (COMException ex) {
            if (ex.ErrorCode != unchecked((int)0x800401E3)) throw;
            app = (ISldWorks)Activator.CreateInstance(Type.GetTypeFromProgID("SldWorks.Application", true));
            ownsApp = true;
        }
        try {
            if (app.GetDocumentCount() != 0)
                throw new InvalidOperationException("Close open SOLIDWORKS documents before exporting; the exporter must discard temporary visibility changes.");
            app.Visible = true;
            oldAP = app.GetUserPreferenceIntegerValue((int)swUserPreferenceIntegerValue_e.swStepAP);
            oldGeometry = app.GetUserPreferenceIntegerValue((int)swUserPreferenceIntegerValue_e.swStepExportPreference);
            oldAtomic = app.GetUserPreferenceToggle((int)swUserPreferenceToggle_e.swStepExportAtomicSave);
            preferencesCaptured = true;
            if (!app.SetUserPreferenceIntegerValue((int)swUserPreferenceIntegerValue_e.swStepAP, 214)
                || !app.SetUserPreferenceIntegerValue((int)swUserPreferenceIntegerValue_e.swStepExportPreference,
                    (int)swAcisOutputGeometryPreference_e.swAcisOutputAsSolidAndSurface))
                throw new InvalidOperationException("Cannot set STEP AP214 solid/surface export options.");
            app.SetUserPreferenceToggle((int)swUserPreferenceToggle_e.swStepExportAtomicSave, false);
            if (app.GetUserPreferenceToggle((int)swUserPreferenceToggle_e.swStepExportAtomicSave))
                throw new InvalidOperationException("Cannot set self-contained assembly STEP output.");
        } catch { Dispose(); throw; }
    }

    private static object[] Items(object value) { return value as object[] ?? new object[0]; }

    private static void Inspect(IComponent2 parent, List<IComponent2> hidden, List<IComponent2> visible, List<string> audit)
    {
        foreach (object item in Items(parent.GetChildren())) {
            IComponent2 child = (IComponent2)item;
            if (child.IsSuppressed()) { audit.Add("Suppressed: " + child.Name2); continue; }
            if (child.IsHidden(false)) { hidden.Add(child); audit.Add("Hidden: " + child.Name2); continue; }
            IModelDoc2 model = (IModelDoc2)child.GetModelDoc2();
            if (model == null) throw new InvalidOperationException("Visible component is unresolved: " + child.Name2);
            if (model.Extension.IsFutureVersion()) throw new InvalidOperationException("Newer-version visible component: " + child.Name2);
            visible.Add(child);
            Inspect(child, hidden, visible, audit);
        }
    }

    private static GeometryTotals Measure(IModelDoc2 doc)
    {
        IMassProperty mass = (IMassProperty)doc.Extension.CreateMassProperty();
        if (mass == null) throw new InvalidOperationException("Cannot measure native geometry.");
        mass.UseSystemUnits = true;
        return new GeometryTotals { volume_mm3 = mass.Volume * 1e9, area_mm2 = mass.SurfaceArea * 1e6 };
    }

    public ExportResult Export(string source, string destination)
    {
        ExportResult row = new ExportResult();
        row.source = source;
        row.output = destination;
        string tempDir = null;
        try {
            int kind = Path.GetExtension(source).Equals(".sldasm", StringComparison.OrdinalIgnoreCase) ? 2 : 1;
            app.SetCurrentWorkingDirectory(Path.GetDirectoryName(source));
            int errors=0, warnings=0;
            IModelDoc2 doc = app.OpenDoc6(source, kind, 67, "", ref errors, ref warnings);
            row.openErrors=errors; row.openWarnings=warnings;
            if ((errors & (int)swFileLoadError_e.swFutureVersion) != 0)
                throw new InvalidOperationException("Newer-version file: installed SOLIDWORKS " + app.RevisionNumber() + " cannot open this model. Use SOLIDWORKS 2026 or newer for the supplied examples.");
            if (doc == null || errors != 0) throw new InvalidOperationException("Open failed or references missing (errors="+errors+", warnings="+warnings+").");
            // Read-only is intentional; other warnings may indicate substituted configurations or missing geometry.
            if ((warnings & ~(int)swFileLoadWarning_e.swFileLoadWarning_ReadOnly) != 0)
                throw new InvalidOperationException("Load warnings require repair: "+warnings);
            if (doc.Extension.IsFutureVersion()) throw new InvalidOperationException("File was saved in a newer SOLIDWORKS version.");
            int activateErrors=0;
            IModelDoc2 active = (IModelDoc2)app.ActivateDoc3(source, false, (int)swRebuildOnActivation_e.swDontRebuildActiveDoc, ref activateErrors);
            if (active == null || activateErrors != 0) throw new InvalidOperationException("Cannot activate source: "+activateErrors);
            IConfiguration config = (IConfiguration)doc.ConfigurationManager.ActiveConfiguration;
            row.configuration = config.Name;
            List<string> audit = new List<string>();
            if (kind == 2) {
                ((IAssemblyDoc)doc).ResolveAllLightWeightComponents(false);
                IComponent2 root = (IComponent2)config.GetRootComponent3(true);
                if (root == null) throw new InvalidOperationException("Assembly root unavailable.");
                List<IComponent2> hidden = new List<IComponent2>(), visible = new List<IComponent2>();
                Inspect(root, hidden, visible, audit);
                foreach (IComponent2 component in hidden) {
                    component.SetSuppression2((int)swComponentSuppressionState_e.swComponentSuppressed);
                    if (!component.IsSuppressed()) throw new InvalidOperationException("Cannot exclude hidden component: "+component.Name2);
                }
                foreach (IComponent2 component in visible) {
                    if (component.IsSuppressed() || component.GetModelDoc2() == null)
                        throw new InvalidOperationException("Hidden-component suppression also affected visible instance "+component.Name2+". Use separate configurations for those instances.");
                }
            }
            row.excluded = audit.ToArray();
            doc.ClearSelection2(true);
            if (!doc.Extension.SetUserPreferenceString((int)swUserPreferenceStringValue_e.swFileSaveAsCoordinateSystem, 0, ""))
                throw new InvalidOperationException("Cannot set default export coordinates.");
            row.nativeGeometry = Measure(doc);
            Directory.CreateDirectory(Path.GetDirectoryName(destination));
            tempDir = Path.Combine(Path.GetDirectoryName(destination), ".export-"+Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(tempDir);
            string temp = Path.Combine(tempDir, "model.step");
            errors=0; warnings=0;
            bool saved = doc.Extension.SaveAs(temp, 0, 1, null, ref errors, ref warnings);
            row.saveErrors=errors; row.saveWarnings=warnings;
            if (!saved || errors!=0 || warnings!=0 || !File.Exists(temp))
                throw new InvalidOperationException("STEP save failed or warned (errors="+errors+", warnings="+warnings+").");
            foreach (string path in Directory.GetFiles(tempDir,"*.err"))
                if (new FileInfo(path).Length>0) throw new InvalidOperationException("Translator error: "+File.ReadAllText(path));
            if (Directory.GetFiles(tempDir,"*.step").Length + Directory.GetFiles(tempDir,"*.stp").Length != 1)
                throw new InvalidOperationException("Assembly STEP unexpectedly uses external component files.");
            bool geometry=false, complete=false;
            using (StreamReader reader=File.OpenText(temp)) {
                if (reader.ReadLine()!="ISO-10303-21;") throw new InvalidOperationException("Not a STEP file.");
                string line;
                while ((line=reader.ReadLine())!=null) {
                    if (line.Contains("MANIFOLD_SOLID_BREP") || line.Contains("SHELL_BASED_SURFACE_MODEL") || line.Contains("FACETED_BREP")) geometry=true;
                    if (line.Trim()=="END-ISO-10303-21;") complete=true;
                }
            }
            if (!geometry || !complete) throw new InvalidOperationException("STEP has no solid/surface geometry or is incomplete.");
            if (File.Exists(destination)) File.Replace(temp,destination,null);
            else File.Move(temp,destination);
            row.status="exported";
            row.message="STEP AP214; last-saved configuration/display state. Geometry comparison is recorded separately.";
        } catch (Exception ex) {
            row.message=ex.Message;
        } finally {
            if (tempDir!=null && Directory.Exists(tempDir)) Directory.Delete(tempDir,true);
            if (!app.CloseAllDocuments(true)) throw new InvalidOperationException("Cannot discard session documents; stopping to prevent cross-model contamination.");
        }
        return row;
    }

    public void Dispose()
    {
        if (app==null) return;
        try {
            if (preferencesCaptured) {
                app.SetUserPreferenceIntegerValue((int)swUserPreferenceIntegerValue_e.swStepAP,oldAP);
                app.SetUserPreferenceIntegerValue((int)swUserPreferenceIntegerValue_e.swStepExportPreference,oldGeometry);
                app.SetUserPreferenceToggle((int)swUserPreferenceToggle_e.swStepExportAtomicSave,oldAtomic);
            }
        } finally {
            try { if (ownsApp) app.ExitApp(); }
            finally { Marshal.FinalReleaseComObject(app); app=null; }
        }
    }
}

public sealed class GeometryTotals { public double volume_mm3; public double area_mm2; }
public sealed class ExportResult
{
    public string source, output, configuration="", status="failed", message="";
    public string[] excluded = new string[0];
    public int openErrors, openWarnings, saveErrors, saveWarnings;
    public GeometryTotals nativeGeometry;
}
