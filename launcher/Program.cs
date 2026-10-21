using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace GhostData.Launcher;

internal static class Program
{
    [STAThread]
    private static void Main()
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        Application.Run(new LauncherWindow());
    }
}

internal sealed class LauncherWindow : Form
{
    private readonly Label _status = new() { AutoSize = true, Font = new Font("Segoe UI Semibold", 11f) };
    private readonly RichTextBox _log = new() { ReadOnly = true, BackColor = Color.FromArgb(16, 20, 18), ForeColor = Color.Gainsboro, BorderStyle = BorderStyle.None, Font = new Font("Consolas", 9f), Dock = DockStyle.Fill };
    private readonly ProgressBar _progress = new() { Style = ProgressBarStyle.Marquee, MarqueeAnimationSpeed = 25, Dock = DockStyle.Fill };
    private readonly Button _runAgain = new() { Text = "Run again", Enabled = false, AutoSize = true };
    private readonly Button _close = new() { Text = "Close", AutoSize = true };
    private bool _running;

    public LauncherWindow()
    {
        Text = "GhostData — Verify, Build & Launch";
        ClientSize = new Size(760, 480);
        MinimumSize = new Size(620, 400);
        StartPosition = FormStartPosition.CenterScreen;
        BackColor = Color.FromArgb(29, 35, 31);
        ForeColor = Color.WhiteSmoke;

        var layout = new TableLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(18), RowCount = 4, ColumnCount = 1 };
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 22));
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        layout.Controls.Add(_status, 0, 0);
        layout.Controls.Add(_progress, 0, 1);
        layout.Controls.Add(_log, 0, 2);

        var buttons = new FlowLayoutPanel { Dock = DockStyle.Fill, AutoSize = true, FlowDirection = FlowDirection.RightToLeft, Padding = new Padding(0, 8, 0, 0) };
        buttons.Controls.Add(_close);
        buttons.Controls.Add(_runAgain);
        layout.Controls.Add(buttons, 0, 3);
        Controls.Add(layout);

        _close.Click += (_, _) => Close();
        _runAgain.Click += async (_, _) => await ExecuteAsync();
        Shown += async (_, _) => await ExecuteAsync();
    }

    private async Task ExecuteAsync()
    {
        if (_running) return;
        _running = true;
        _runAgain.Enabled = false;
        _progress.Style = ProgressBarStyle.Marquee;
        _log.Clear();
        try
        {
            var root = AppDomain.CurrentDomain.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar);
            RequireFile(root, "Build-GhostData.cmd");
            RequireFile(root, "Run-GhostData.cmd");
            RequireFile(root, "ghostdata.py");

            var python = ResolvePython();
            SetStatus("1/3 — Running GhostData tests…");
            Append($"> \"{python.FileName}\" {python.Prefix}-m unittest discover -s tests -p test_*.py -q\r\n");
            var testExit = await RunProcessAsync(python.FileName, python.Prefix + "-m unittest discover -s tests -p test_*.py -q", root);
            if (testExit != 0) throw new InvalidOperationException($"Tests failed with exit code {testExit}.");

            SetStatus("2/3 — Building sensor and dashboard…");
            Append("\r\n> Build-GhostData.cmd\r\n");
            var build = Path.Combine(root, "Build-GhostData.cmd");
            var buildExit = await RunProcessAsync(
                Environment.GetEnvironmentVariable("COMSPEC") ?? "cmd.exe",
                "/d /s /c \"\"" + build + "\"\"",
                root,
                skipLauncherBuild: true);
            if (buildExit != 0) throw new InvalidOperationException($"Build failed with exit code {buildExit}.");

            SetStatus("3/3 — Launching GhostData…");
            Append("\r\nAll tests passed and the build succeeded. Launching GhostData…\r\n");
            Process.Start(new ProcessStartInfo { FileName = Path.Combine(root, "Run-GhostData.cmd"), WorkingDirectory = root, UseShellExecute = true });
            SetStatus("GhostData launched successfully.");
            _progress.Style = ProgressBarStyle.Continuous;
            _progress.Value = 100;
            _runAgain.Enabled = true;
        }
        catch (Exception ex)
        {
            SetStatus("GhostData did not launch.");
            Append("\r\nERROR: " + ex.Message + "\r\n");
            _progress.Style = ProgressBarStyle.Continuous;
            _progress.Value = 0;
            _runAgain.Enabled = true;
            MessageBox.Show(this, ex.Message, "GhostData launch failed", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
        finally { _running = false; }
    }

    private async Task<int> RunProcessAsync(string fileName, string arguments, string workingDirectory, bool skipLauncherBuild = false)
    {
        using var process = new Process
        {
            StartInfo = new ProcessStartInfo
            {
                FileName = fileName, Arguments = arguments, WorkingDirectory = workingDirectory,
                UseShellExecute = false, CreateNoWindow = true,
                RedirectStandardOutput = true, RedirectStandardError = true,
            },
            EnableRaisingEvents = true,
        };
        if (skipLauncherBuild)
            process.StartInfo.EnvironmentVariables["GHOSTDATA_SKIP_LAUNCHER"] = "1";
        process.OutputDataReceived += (_, e) => { if (e.Data != null) Append(e.Data + "\r\n"); };
        process.ErrorDataReceived += (_, e) => { if (e.Data != null) Append(e.Data + "\r\n"); };
        if (!process.Start()) throw new InvalidOperationException("Could not start " + fileName + ".");
        process.BeginOutputReadLine();
        process.BeginErrorReadLine();
        await Task.Run(() => process.WaitForExit());
        process.WaitForExit();
        return process.ExitCode;
    }

    private static (string FileName, string Prefix) ResolvePython()
    {
        var candidates = new List<string?>
        {
            Environment.GetEnvironmentVariable("GHOSTDATA_PYTHON"),
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "Python", "Python312", "python.exe"),
            FindOnPath("py.exe"), FindOnPath("python.exe"),
        };
        foreach (var candidate in candidates.Where(x => !string.IsNullOrWhiteSpace(x)))
        {
            var value = candidate!;
            if (!File.Exists(value)) continue;
            return (value, Path.GetFileName(value).Equals("py.exe", StringComparison.OrdinalIgnoreCase) ? "-3.12 " : "");
        }
        throw new FileNotFoundException("Python 3.12 or newer was not found. Install Python or set GHOSTDATA_PYTHON.");
    }

    private static string? FindOnPath(string executable)
    {
        foreach (var folder in (Environment.GetEnvironmentVariable("PATH") ?? "").Split(Path.PathSeparator))
        {
            try
            {
                var candidate = Path.Combine(folder.Trim(), executable);
                if (File.Exists(candidate) && candidate.IndexOf("WindowsApps", StringComparison.OrdinalIgnoreCase) < 0) return candidate;
            }
            catch { }
        }
        return null;
    }

    private static void RequireFile(string root, string relative)
    {
        if (!File.Exists(Path.Combine(root, relative))) throw new FileNotFoundException($"Required GhostData file is missing: {relative}");
    }

    private void SetStatus(string value)
    {
        if (InvokeRequired) { BeginInvoke(new Action<string>(SetStatus), value); return; }
        _status.Text = value;
    }

    private void Append(string value)
    {
        if (InvokeRequired) { BeginInvoke(new Action<string>(Append), value); return; }
        _log.AppendText(value);
        _log.SelectionStart = _log.TextLength;
        _log.ScrollToCaret();
    }
}
