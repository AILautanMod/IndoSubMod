using System;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Text;
using System.Text.RegularExpressions;
using System.Collections.Generic;
using System.Windows.Forms;
using Microsoft.Win32;
using System.Runtime.InteropServices;

internal sealed class InstallerForm : Form
{
    private const string Version = "__APP_VERSION__";
    private readonly Color bg = Color.FromArgb(5, 12, 22);
    private readonly Color panel = Color.FromArgb(10, 23, 38);
    private readonly Color cyan = Color.FromArgb(0, 190, 255);
    private readonly Color gold = Color.FromArgb(255, 183, 66);
    private readonly Label stageLabel = new Label();
    private readonly Label detailLabel = new Label();
    private readonly Label percentLabel = new Label();
    private readonly Label footerLabel = new Label();
    private readonly TextBox installPathBox = new TextBox();
    private readonly Button browseButton = new Button();
    private readonly Panel componentsBox = new Panel();
    private readonly CheckBox coreComponentBox = new CheckBox();
    private readonly CheckBox speechModelBox = new CheckBox();
    private readonly CheckBox offlineModelBox = new CheckBox();
    private readonly CheckBox desktopShortcutBox = new CheckBox();
    private readonly Label agreementText = new Label();
    private readonly NeonProgressBar progress = new NeonProgressBar();
    private readonly Button closeButton = new Button();
    private readonly Button logButton = new Button();
    private readonly Button supportButton = new Button();
    private readonly Timer animation = new Timer();
    private readonly Image bannerImage;
    private readonly Image logoImage;
    private readonly StringBuilder errors = new StringBuilder();
    private readonly HashSet<Button> pressedButtons = new HashSet<Button>();
    private Process child;
    private string workDirectory;
    private string logPath;
    private int targetPercent = 2;
    private int currentPercent = 0;
    private int lastReportedPercent = 0;
    private double displayedPercent;
    private int progressReportBaseline;
    private DateTime lastProgressReportAt = DateTime.MinValue;
    private string currentOperation = "Preparing setup (Menyiapkan pemasang)";
    private DateTime operationStarted = DateTime.Now;
    private DateTime overallStarted = DateTime.MinValue;
    private bool finished;
    private bool installStarted;
    private bool termsAccepted;
    private string installerPhase = "Waiting to start setup (Menunggu pemasangan dimulai)";
    private const int CaptionHeight = 42;
    [DllImport("user32.dll")] private static extern bool ReleaseCapture();
    [DllImport("user32.dll")] private static extern IntPtr SendMessage(IntPtr hWnd, int msg, IntPtr wParam, IntPtr lParam);

    public InstallerForm()
    {
        Text = "IndoSubMod Setup v" + Version;
        AutoScaleMode = AutoScaleMode.None;
        Size = new Size(1280, 970);
        MinimumSize = new Size(1280, 940);
        StartPosition = FormStartPosition.CenterScreen;
        BackColor = bg;
        ForeColor = Color.White;
        Font = new Font("Segoe UI", 10.5F);
        FormBorderStyle = FormBorderStyle.Sizable;
        MaximizeBox = true;
        MinimizeBox = true;
        TopMost = true;
        ShowInTaskbar = true;
        try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch { }

        using (Stream bannerStream = Assembly.GetExecutingAssembly().GetManifestResourceStream("IndoSubModBanner.png"))
        {
            if (bannerStream != null) using (Image loaded = Image.FromStream(bannerStream)) bannerImage = new Bitmap(loaded);
        }
        using (Stream logoStream = Assembly.GetExecutingAssembly().GetManifestResourceStream("IndoSubModLogo.png"))
        {
            if (logoStream != null) using (Image loaded = Image.FromStream(logoStream)) logoImage = new Bitmap(loaded);
        }
        Panel hero = new Panel();
        hero.BackColor = panel;
        hero.Location = new Point(18, 18);
        hero.Size = new Size(1244, 170);
        if (bannerImage != null) { hero.BackgroundImage = bannerImage; hero.BackgroundImageLayout = ImageLayout.Stretch; }
        Controls.Add(hero);

        Label brand = new Label();
        brand.Text = "IndoSubMod";
        brand.Font = new Font("Segoe UI Semibold", 58F, FontStyle.Bold);
        brand.ForeColor = Color.White;
        brand.AutoSize = true;
        brand.Location = new Point(26, 14);
        brand.Visible = false;
        hero.Controls.Add(brand);
        if (logoImage != null)
        {
            PictureBox wordmark = new PictureBox();
            wordmark.Location = new Point(28, 18);
            wordmark.Size = new Size(390, 111);
            wordmark.BackColor = Color.Transparent;
            wordmark.Paint += delegate(object sender, PaintEventArgs e)
            {
                e.Graphics.SmoothingMode = SmoothingMode.HighQuality;
                e.Graphics.DrawImage(logoImage, new Rectangle(0, 0, wordmark.Width, wordmark.Height), new Rectangle(100, 800, 1054, 300), GraphicsUnit.Pixel);
            };
            hero.Controls.Add(wordmark);
        }

        Label tagline = new Label();
        tagline.Text = "AI VIDEO TRANSLATOR   •   BY AI LAUTAN MOD";
        tagline.Font = new Font("Segoe UI", 10F);
        tagline.ForeColor = Color.FromArgb(173, 191, 208);
        tagline.AutoSize = true;
        tagline.Location = new Point(240, 100);
        tagline.Visible = false;
        hero.Controls.Add(tagline);

        Panel versionPanel = new Panel();
        versionPanel.Location = new Point(450, 16);
        versionPanel.Size = new Size(250, 62);
        versionPanel.BackColor = Color.FromArgb(5, 12, 22);
        versionPanel.Paint += delegate(object sender, PaintEventArgs e) { DrawRoundedBorder(e.Graphics, versionPanel.ClientRectangle, Color.FromArgb(0, 190, 255), 1.5F); };
        hero.Controls.Add(versionPanel);

        Label versionLabel = new Label();
        versionLabel.Text = "Version " + Version;
        versionLabel.Font = new Font("Segoe UI Semibold", 18F, FontStyle.Bold);
        versionLabel.ForeColor = gold;
        versionLabel.AutoSize = false;
        versionLabel.Location = new Point(12, 4);
        versionLabel.Size = new Size(224, 30);
        versionLabel.BackColor = Color.Transparent;
        FitLabelToBounds(versionLabel);
        versionPanel.Controls.Add(versionLabel);
        Label versionTranslation = new Label();
        versionTranslation.Text = "Versi " + Version;
        versionTranslation.Font = new Font("Segoe UI", 11F, FontStyle.Regular);
        versionTranslation.ForeColor = Color.FromArgb(193, 219, 236);
        versionTranslation.AutoSize = false;
        versionTranslation.Location = new Point(13, 34);
        versionTranslation.Size = new Size(224, 21);
        versionTranslation.BackColor = Color.Transparent;
        FitLabelToBounds(versionTranslation);
        versionPanel.Controls.Add(versionTranslation);
        Label heroSubtitle = new Label();
        heroSubtitle.Text = "Application installer\r\n(Pemasang aplikasi)";
        heroSubtitle.Font = new Font("Segoe UI", 12F);
        heroSubtitle.ForeColor = Color.FromArgb(190, 208, 224);
        heroSubtitle.AutoSize = false;
        heroSubtitle.Size = new Size(500, 58);
        heroSubtitle.Location = new Point(455, 88);
        heroSubtitle.BackColor = Color.Transparent;
        hero.Controls.Add(heroSubtitle);

        Panel pathCard = CreateCard(new Point(28, 202), new Size(1224, 72), gold);
        Controls.Add(pathCard);
        Label pathLabel = new Label();
        pathLabel.Text = "Install folder\r\n(Folder instalasi)";
        pathLabel.Location = new Point(20, 9);
        pathLabel.Size = new Size(190, 54);
        pathLabel.Font = new Font("Segoe UI Semibold", 10F, FontStyle.Bold);
        pathLabel.ForeColor = Color.FromArgb(220, 230, 240);
        pathCard.Controls.Add(pathLabel);
        FitLabelToBounds(pathLabel);
        AddVisualIcon(pathCard, "folder", new Point(224, 12), new Size(44, 44), gold);

        installPathBox.Text = GetDefaultInstallPath();
        installPathBox.Location = new Point(290, 16);
        installPathBox.Size = new Size(750, 36);
        installPathBox.BackColor = panel;
        installPathBox.ForeColor = Color.White;
        installPathBox.BorderStyle = BorderStyle.FixedSingle;
        pathCard.Controls.Add(installPathBox);

        browseButton.Text = "Browse (Telusuri)";
        browseButton.Location = new Point(1055, 14);
        browseButton.Size = new Size(150, 40);
        browseButton.FlatStyle = FlatStyle.Flat;
        browseButton.FlatAppearance.BorderColor = Color.FromArgb(43, 78, 104);
        browseButton.BackColor = panel;
        browseButton.ForeColor = Color.White;
        AnimateButton(browseButton);
        browseButton.Click += delegate { BrowseForInstallPath(); };
        pathCard.Controls.Add(browseButton);

        componentsBox.Location = new Point(22, 284);
        componentsBox.Size = new Size(1236, 286);
        componentsBox.BackColor = Color.FromArgb(7, 18, 30);
        componentsBox.Paint += delegate(object sender, PaintEventArgs e) { DrawRoundedBorder(e.Graphics, componentsBox.ClientRectangle, gold, 1.4F); };
        Controls.Add(componentsBox);
        Label componentsHeading = new Label();
        componentsHeading.Text = "IndoSubMod components (Komponen IndoSubMod)";
        componentsHeading.Location = new Point(72, 10);
        componentsHeading.Size = new Size(900, 34);
        componentsHeading.Font = new Font("Segoe UI Semibold", 15F, FontStyle.Bold);
        componentsHeading.ForeColor = Color.White;
        componentsBox.Controls.Add(componentsHeading);
        FitLabelToBounds(componentsHeading);
        AddVisualIcon(componentsBox, "package", new Point(22, 9), new Size(42, 34), cyan);
        AddComponentRow(coreComponentBox, "python", "Application, Python, and libraries (required)", "Required to run IndoSubMod. (Diperlukan untuk menjalankan IndoSubMod.)", 50, 54);
        coreComponentBox.Checked = true; coreComponentBox.Enabled = false;
        AddComponentRow(speechModelBox, "wave", "Whisper small speech recognition (required)", "Creates English subtitles from video speech. (Membuat subtitle Inggris dari ucapan di video.)", 108, 54);
        speechModelBox.Checked = true; speechModelBox.Enabled = false;
        AddComponentRow(offlineModelBox, "translate", "Offline translation en → id (Argos)", "Enables translation without internet; GPT online remains available if unchecked. (Terjemahan luring; GPT daring tetap tersedia.)", 166, 54);
        offlineModelBox.Checked = true;
        AddComponentRow(desktopShortcutBox, "monitor", "IndoSubMod desktop shortcut", "A shortcut for quick access. (Pintasan untuk menjalankan aplikasi dengan cepat.)", 224, 54);
        desktopShortcutBox.Checked = true;

        agreementText.Text = "Prototype for evaluation only; not for commercial use. This app does not grant rights to sell, alter, or distribute selected videos. The source file is unchanged: a separate MKV with a subtitle track is created; video and audio are not re-encoded. Video rights remain with their owners. Third-party software and model licenses still apply.\r\nPrototipe hanya untuk evaluasi; bukan untuk penggunaan komersial. Aplikasi ini tidak memberikan hak untuk menjual, mengubah, atau mendistribusikan video yang dipilih. File sumber tidak diubah: file MKV terpisah dengan trek subtitle dibuat; video dan audio tidak dikodekan ulang. Hak video tetap pada pemiliknya. Lisensi perangkat lunak dan model pihak ketiga tetap berlaku.";
        agreementText.Location = new Point(40, 576);
        agreementText.Size = new Size(1168, 88);
        agreementText.ForeColor = Color.FromArgb(190, 208, 224);
        agreementText.BackColor = bg;
        agreementText.Font = new Font("Segoe UI", 8.5F);
        agreementText.Cursor = Cursors.Default;
        Controls.Add(agreementText);
        FitLabelToBounds(agreementText);

        stageLabel.Text = "Review the installation terms (Tinjau ketentuan instalasi)";
        stageLabel.Font = new Font("Segoe UI Semibold", 12F, FontStyle.Bold);
        stageLabel.ForeColor = Color.White;
        stageLabel.AutoSize = false;
        stageLabel.Location = new Point(96, 670);
        stageLabel.Size = new Size(1050, 28);
        FitLabelToBounds(stageLabel);
        Controls.Add(stageLabel);
        AddVisualIcon(this, "gear", new Point(34, 653), new Size(48, 48), gold);

        detailLabel.Text = "Clicking Install means you accept the terms above. (Klik Instal berarti Anda menyetujui ketentuan di atas.)";
        detailLabel.Font = new Font("Segoe UI", 9.5F);
        detailLabel.ForeColor = Color.FromArgb(151, 170, 189);
        detailLabel.Location = new Point(96, 699);
        detailLabel.Size = new Size(1120, 42);
        FitLabelToBounds(detailLabel);
        Controls.Add(detailLabel);

        progress.Location = new Point(40, 746);
        progress.Size = new Size(1100, 22);
        progress.Minimum = 0;
        progress.Maximum = 10000;
        progress.Value = 0;
        progress.Style = ProgressBarStyle.Continuous;
        progress.GlowColor = cyan;
        Controls.Add(progress);

        percentLabel.Text = "0%";
        percentLabel.Font = new Font("Segoe UI Semibold", 13F, FontStyle.Bold);
        percentLabel.ForeColor = cyan;
        percentLabel.Location = new Point(1147, 743);
        percentLabel.Size = new Size(82, 28);
        percentLabel.TextAlign = ContentAlignment.MiddleLeft;
        Controls.Add(percentLabel);

        footerLabel.Text = "Click Install to accept the terms and continue. (Klik Instal untuk menyetujui ketentuan dan melanjutkan.)";
        footerLabel.Font = new Font("Segoe UI", 9.5F);
        footerLabel.ForeColor = Color.FromArgb(118, 139, 158);
        footerLabel.Location = new Point(40, 774);
        footerLabel.Size = new Size(1165, 28);
        FitLabelToBounds(footerLabel);
        Controls.Add(footerLabel);

        logButton.Text = "▤  Log (Log)";
        logButton.Location = new Point(40, 804);
        logButton.Size = new Size(210, 42);
        logButton.FlatStyle = FlatStyle.Flat;
        logButton.FlatAppearance.BorderColor = Color.FromArgb(43, 78, 104);
        logButton.BackColor = panel;
        logButton.ForeColor = Color.FromArgb(190, 208, 224);
        AnimateButton(logButton);
        logButton.Enabled = true;
        logButton.Click += delegate { OpenLog(); };
        Controls.Add(logButton);

        supportButton.Text = "Support the creator\r\n(Dukung kreator)";
        supportButton.Location = new Point(650, 801);
        supportButton.Size = new Size(260, 61);
        supportButton.FlatStyle = FlatStyle.Flat;
        supportButton.FlatAppearance.BorderSize = 0;
        supportButton.Font = new Font("Segoe UI Semibold", 10F, FontStyle.Bold);
        supportButton.Cursor = Cursors.Hand;
        AnimateButton(supportButton);
        supportButton.Paint += DrawGoldButton;
        supportButton.MouseEnter += delegate { supportButton.Invalidate(); };
        supportButton.MouseLeave += delegate { supportButton.Invalidate(); };
        supportButton.Visible = true;
        supportButton.Click += delegate
        {
            try { Process.Start(new ProcessStartInfo("https://buymeacoffee.com/ailautanmod") { UseShellExecute = true }); }
            catch (Exception ex) { ShowInstallerDialog("Could not open the support page (Halaman dukungan tidak dapat dibuka)", ex.Message, true); }
        };
        Controls.Add(supportButton);

        closeButton.Text = "";
        closeButton.AccessibleName = "Accept the terms and install (Setujui ketentuan dan instal)";
        closeButton.Location = new Point(935, 801);
        closeButton.Size = new Size(280, 61);
        closeButton.FlatStyle = FlatStyle.Flat;
        closeButton.FlatAppearance.BorderSize = 0;
        closeButton.BackColor = gold;
        closeButton.ForeColor = Color.FromArgb(26, 17, 5);
        closeButton.Font = new Font("Segoe UI Semibold", 14F, FontStyle.Bold);
        AnimateButton(closeButton);
        closeButton.Paint += DrawGoldButton;
        closeButton.Enabled = true;
        closeButton.Click += delegate { if (finished) Close(); else if (!installStarted) { termsAccepted = true; BeginInstall(); } };
        Controls.Add(closeButton);

        animation.Interval = 100;
        animation.Tick += delegate
        {
            if (installStarted && !finished)
            {
                UpdateSmoothProgress();
                UpdateActivityDetail();
            }
        };
        animation.Start();
    }

    private void ConfigureComponentCheckBox(CheckBox checkBox, string label, int x, int y)
    {
        checkBox.Text = label;
        checkBox.Location = new Point(x, y);
        checkBox.Size = new Size(820, 25);
        checkBox.ForeColor = Color.White;
        checkBox.BackColor = bg;
        componentsBox.Controls.Add(checkBox);
    }

    private void AddComponentRow(CheckBox checkBox, string icon, string title, string description, int y, int height)
    {
        Panel row = new Panel();
        row.Location = new Point(22, y);
        row.Size = new Size(1190, height);
        row.BackColor = Color.FromArgb(5, 16, 28);
        componentsBox.Controls.Add(row);
        checkBox.Text = "";
        checkBox.Location = new Point(10, 14);
        checkBox.Size = new Size(26, 26);
        checkBox.Font = new Font("Segoe UI Semibold", 11F, FontStyle.Bold);
        checkBox.ForeColor = Color.White;
        checkBox.BackColor = row.BackColor;
        row.Controls.Add(checkBox);
        AddVisualIcon(row, icon, new Point(57, 3), new Size(54, 48), icon == "python" ? gold : cyan);
        Label heading = new Label();
        heading.Text = title;
        heading.Location = new Point(135, 2);
        heading.Size = new Size(1000, 26);
        heading.Font = new Font("Segoe UI Semibold", 10F, FontStyle.Bold);
        heading.ForeColor = Color.White;
        row.Controls.Add(heading);
        FitLabelToBounds(heading);
        Label detail = new Label();
        detail.Text = description;
        detail.Location = new Point(135, 28);
        detail.Size = new Size(1000, 26);
        detail.Font = new Font("Segoe UI", 8F);
        detail.ForeColor = Color.FromArgb(173, 195, 218);
        row.Controls.Add(detail);
        FitLabelToBounds(detail);
    }

    private void AddVisualIcon(Control parent, string kind, Point location, Size size, Color accent)
    {
        PictureBox icon = new PictureBox();
        icon.Location = location;
        icon.Size = size;
        icon.BackColor = Color.Transparent;
        icon.Paint += delegate(object sender, PaintEventArgs e) { DrawVisualIcon(kind, e.Graphics, icon.ClientRectangle, accent); };
        parent.Controls.Add(icon);
    }

    private void DrawVisualIcon(string kind, Graphics g, Rectangle r, Color accent)
    {
        g.SmoothingMode = SmoothingMode.AntiAlias;
        g.PixelOffsetMode = PixelOffsetMode.HighQuality;
        float scale = Math.Min(r.Width, r.Height) / 96F;
        g.TranslateTransform((r.Width - 96F * scale) / 2F, (r.Height - 96F * scale) / 2F);
        g.ScaleTransform(scale, scale);
        using (Pen cyanPen = new Pen(Color.FromArgb(0, 190, 255), 4F))
        using (Pen palePen = new Pen(Color.FromArgb(218, 239, 249), 3F))
        using (Pen goldPen = new Pen(Color.FromArgb(255, 183, 66), 4F))
        using (SolidBrush cyanFill = new SolidBrush(Color.FromArgb(24, 0, 190, 255)))
        using (SolidBrush goldFill = new SolidBrush(Color.FromArgb(30, 255, 183, 66)))
        using (SolidBrush darkFill = new SolidBrush(Color.FromArgb(10, 23, 38)))
        {
            cyanPen.StartCap = cyanPen.EndCap = LineCap.Round;
            cyanPen.LineJoin = LineJoin.Round;
            palePen.StartCap = palePen.EndCap = LineCap.Round;
            palePen.LineJoin = LineJoin.Round;
            goldPen.StartCap = goldPen.EndCap = LineCap.Round;
            goldPen.LineJoin = LineJoin.Round;
            if (kind == "folder")
            {
                PointF[] folder = { new PointF(12,28), new PointF(12,28), new PointF(12,22), new PointF(18,22), new PointF(39,22), new PointF(47,31), new PointF(78,31), new PointF(84,37), new PointF(84,71), new PointF(78,77), new PointF(18,77), new PointF(12,71) };
                using (GraphicsPath p = new GraphicsPath()) { p.AddLines(folder); p.CloseFigure(); g.FillPath(goldFill, p); g.DrawPath(goldPen, p); }
                g.DrawLine(goldPen, 13, 40, 83, 40);
                RectangleF doc = new RectangleF(47, 50, 18, 25);
                g.FillRectangle(darkFill, doc); g.DrawRectangle(palePen, doc.X, doc.Y, doc.Width, doc.Height);
                g.DrawLine(cyanPen, 52, 57, 60, 57); g.DrawLine(cyanPen, 52, 63, 60, 63);
                g.DrawLine(cyanPen, 56, 45, 56, 51); g.DrawLine(cyanPen, 51, 48, 56, 43); g.DrawLine(cyanPen, 61, 48, 56, 43);
            }
            else if (kind == "wave")
            {
                float[] heights = { 12, 24, 36, 56, 40, 24, 12 };
                for (int i = 0; i < heights.Length; i++) { float x = 16 + i * 12; g.DrawLine(cyanPen, x, 48 - heights[i] / 2, x, 48 + heights[i] / 2); }
                g.DrawLine(palePen, 8, 48, 13, 48); g.DrawLine(palePen, 83, 48, 88, 48);
            }
            else if (kind == "translate")
            {
                DrawRoundRect(g, cyanPen, new RectangleF(9, 15, 51, 42), 8);
                g.DrawLine(cyanPen, 23, 57, 16, 66); g.DrawLine(cyanPen, 16, 66, 32, 57);
                g.DrawLine(palePen, 25, 30, 45, 30); g.DrawLine(palePen, 35, 26, 35, 30);
                g.DrawLine(palePen, 28, 33, 42, 45); g.DrawLine(palePen, 44, 33, 32, 45);
                DrawRoundRect(g, goldPen, new RectangleF(39, 40, 48, 40), 8);
                using (Font languageFont = new Font("Segoe UI", 15F, FontStyle.Bold, GraphicsUnit.Pixel))
                using (SolidBrush goldText = new SolidBrush(Color.FromArgb(255, 183, 66)))
                { g.DrawString("A", languageFont, goldText, 53, 47); }
                g.DrawLine(cyanPen, 44, 73, 48, 73);
            }
            else if (kind == "monitor")
            {
                DrawRoundRect(g, cyanPen, new RectangleF(10, 15, 76, 51), 6);
                g.DrawLine(palePen, 20, 25, 76, 25);
                g.DrawLine(cyanPen, 48, 67, 48, 79); g.DrawLine(cyanPen, 31, 82, 65, 82);
                using (SolidBrush dot = new SolidBrush(Color.FromArgb(255, 183, 66))) { g.FillEllipse(dot, 25, 18, 3, 3); g.FillEllipse(dot, 32, 18, 3, 3); }
            }
            else if (kind == "python")
            {
                using (SolidBrush blue = new SolidBrush(Color.FromArgb(0, 167, 235)))
                using (SolidBrush amber = new SolidBrush(Color.FromArgb(255, 183, 66)))
                {
                    FillRoundRect(g, blue, new RectangleF(30, 12, 36, 35), 9);
                    FillRoundRect(g, amber, new RectangleF(30, 49, 36, 35), 9);
                    g.FillRectangle(blue, 43, 39, 23, 8); g.FillRectangle(amber, 30, 49, 23, 8);
                    g.FillEllipse(Brushes.White, 40, 21, 4, 4); g.FillEllipse(Brushes.White, 53, 70, 4, 4);
                }
            }
            else if (kind == "package")
            {
                PointF[] top = { new PointF(48,12), new PointF(82,29), new PointF(48,47), new PointF(14,29) };
                g.DrawPolygon(cyanPen, top);
                g.DrawLine(cyanPen, 14, 29, 14, 67); g.DrawLine(cyanPen, 14, 67, 48, 84); g.DrawLine(cyanPen, 48, 47, 48, 84);
                g.DrawLine(cyanPen, 82, 29, 82, 67); g.DrawLine(cyanPen, 82, 67, 48, 84);
                g.DrawLine(palePen, 31, 20, 65, 38);
            }
            else if (kind == "gear")
            {
                g.DrawEllipse(goldPen, 28, 28, 40, 40); g.DrawEllipse(goldPen, 40, 40, 16, 16);
                for (int i = 0; i < 8; i++) { double angle = i * Math.PI / 4; g.DrawLine(goldPen, 48 + (float)Math.Cos(angle) * 25, 48 + (float)Math.Sin(angle) * 25, 48 + (float)Math.Cos(angle) * 34, 48 + (float)Math.Sin(angle) * 34); }
            }
        }
        g.ResetTransform();
    }
    private void DrawRoundRect(Graphics g, Pen pen, RectangleF r, float radius)
    {
        using (GraphicsPath path = new GraphicsPath())
        {
            path.AddArc(r.X, r.Y, radius, radius, 180, 90);
            path.AddArc(r.Right - radius, r.Y, radius, radius, 270, 90);
            path.AddArc(r.Right - radius, r.Bottom - radius, radius, radius, 0, 90);
            path.AddArc(r.X, r.Bottom - radius, radius, radius, 90, 90);
            path.CloseFigure();
            g.DrawPath(pen, path);
        }
    }

    private void FillRoundRect(Graphics g, Brush brush, RectangleF r, float radius)
    {
        using (GraphicsPath path = new GraphicsPath())
        {
            path.AddArc(r.X, r.Y, radius, radius, 180, 90);
            path.AddArc(r.Right - radius, r.Y, radius, radius, 270, 90);
            path.AddArc(r.Right - radius, r.Bottom - radius, radius, radius, 0, 90);
            path.AddArc(r.X, r.Bottom - radius, radius, radius, 90, 90);
            path.CloseFigure();
            g.FillPath(brush, path);
        }
    }

    private Panel CreateCard(Point location, Size size, Color border)
    {
        Panel card = new Panel();
        card.Location = location;
        card.Size = size;
        card.BackColor = panel;
        card.Paint += delegate(object sender, PaintEventArgs e) { DrawRoundedBorder(e.Graphics, card.ClientRectangle, border, 1.2F); };
        return card;
    }

    private void BuildChrome()
    {
        Panel content = new Panel();
        content.Location = new Point(0, CaptionHeight);
        content.Size = new Size(ClientSize.Width, ClientSize.Height - CaptionHeight);
        content.BackColor = bg;
        while (Controls.Count > 0)
        {
            Control control = Controls[0];
            Controls.RemoveAt(0);
            content.Controls.Add(control);
        }
        Controls.Add(content);
        Panel caption = new Panel();
        caption.Location = Point.Empty;
        caption.Size = new Size(ClientSize.Width, CaptionHeight);
        caption.BackColor = Color.FromArgb(3, 9, 16);
        caption.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
        caption.Paint += delegate(object sender, PaintEventArgs e) { using (Pen p = new Pen(Color.FromArgb(34, 82, 112), 1F)) e.Graphics.DrawLine(p, 0, caption.Height - 1, caption.Width, caption.Height - 1); };
        PictureBox appIcon = new PictureBox();
        try { if (Icon != null) appIcon.Image = Icon.ToBitmap(); } catch { }
        appIcon.Location = new Point(13, 8);
        appIcon.Size = new Size(26, 26);
        appIcon.SizeMode = PictureBoxSizeMode.Zoom;
        appIcon.BackColor = Color.Transparent;
        caption.Controls.Add(appIcon);
        Label title = new Label();
        title.Text = "IndoSubMod Setup v" + Version;
        title.Location = new Point(49, 0);
        title.Size = new Size(400, CaptionHeight);
        title.TextAlign = ContentAlignment.MiddleLeft;
        title.Font = new Font("Segoe UI Semibold", 10F, FontStyle.Bold);
        title.ForeColor = Color.White;
        title.BackColor = Color.Transparent;
        caption.Controls.Add(title);
        Button minimize = CaptionButton("—", new Point(caption.Width - 132, 0), caption);
        minimize.Anchor = AnchorStyles.Top | AnchorStyles.Right;
        minimize.Click += delegate { WindowState = FormWindowState.Minimized; };
        Button maximize = CaptionButton("□", new Point(caption.Width - 88, 0), caption);
        maximize.Anchor = AnchorStyles.Top | AnchorStyles.Right;
        maximize.Click += delegate { WindowState = WindowState == FormWindowState.Maximized ? FormWindowState.Normal : FormWindowState.Maximized; };
        Button close = CaptionButton("×", new Point(caption.Width - 44, 0), caption);
        close.Anchor = AnchorStyles.Top | AnchorStyles.Right;
        close.Click += delegate { Close(); };
        close.MouseEnter += delegate { close.BackColor = Color.FromArgb(190, 40, 48); };
        close.MouseLeave += delegate { close.BackColor = caption.BackColor; };
        caption.MouseDown += CaptionMouseDown;
        title.MouseDown += CaptionMouseDown;
        appIcon.MouseDown += CaptionMouseDown;
        Controls.Add(caption);
        caption.BringToFront();
    }

    private Button CaptionButton(string text, Point location, Control parent)
    {
        Button button = new Button();
        button.Text = text;
        button.Location = location;
        button.Size = new Size(44, CaptionHeight);
        button.FlatStyle = FlatStyle.Flat;
        button.FlatAppearance.BorderSize = 0;
        button.BackColor = Color.FromArgb(3, 9, 16);
        button.ForeColor = Color.FromArgb(226, 236, 246);
        button.Font = new Font("Segoe UI", text == "×" ? 17F : 11F);
        button.Cursor = Cursors.Hand;
        AnimateButton(button);
        button.MouseEnter += delegate { if (text != "×") button.BackColor = Color.FromArgb(22, 40, 56); };
        button.MouseLeave += delegate { if (text != "×") button.BackColor = Color.FromArgb(3, 9, 16); };
        parent.Controls.Add(button);
        return button;
    }

    private void AnimateButton(Button button)
    {
        float radius = 20F;
        ApplyRoundedButtonRegion(button, radius);
        button.Resize += delegate { ApplyRoundedButtonRegion(button, radius); };
        button.FlatAppearance.MouseDownBackColor = Color.FromArgb(0, 157, 205);
        button.FlatAppearance.MouseOverBackColor = Color.FromArgb(24, 48, 67);
        button.MouseDown += delegate(object sender, MouseEventArgs e)
        {
            if (e.Button != MouseButtons.Left || !button.Enabled) return;
            pressedButtons.Add(button);
            button.Invalidate();
        };
        button.MouseUp += delegate(object sender, MouseEventArgs e)
        {
            if (!pressedButtons.Contains(button)) return;
            Timer pulse = new Timer();
            pulse.Interval = 110;
            pulse.Tick += delegate
            {
                pulse.Stop();
                pulse.Dispose();
                pressedButtons.Remove(button);
                if (!button.IsDisposed) button.Invalidate();
            };
            pulse.Start();
        };
        button.MouseLeave += delegate
        {
            if (!button.Capture && pressedButtons.Remove(button)) button.Invalidate();
        };
    }

    private void ApplyRoundedButtonRegion(Button button, float radius)
    {
        if (button.IsDisposed || button.Width < 2 || button.Height < 2) return;
        using (GraphicsPath path = RoundedPath(new Rectangle(0, 0, button.Width, button.Height), Math.Min(radius, Math.Min(button.Width, button.Height) / 2F)))
        {
            Region replacement = new Region(path);
            Region previous = button.Region;
            button.Region = replacement;
            if (previous != null) previous.Dispose();
        }
    }

    private void CaptionMouseDown(object sender, MouseEventArgs e)
    {
        if (e.Button != MouseButtons.Left) return;
        ReleaseCapture();
        SendMessage(Handle, 0xA1, new IntPtr(2), IntPtr.Zero);
    }

    private void DrawGoldButton(object sender, PaintEventArgs e)
    {
        Button button = (Button)sender;
        Graphics g = e.Graphics;
        g.SmoothingMode = SmoothingMode.AntiAlias;
        Rectangle r = new Rectangle(2, 2, button.Width - 5, button.Height - 5);
        using (GraphicsPath path = RoundedPath(r, 20))
        {
        bool hovered = button.ClientRectangle.Contains(button.PointToClient(Cursor.Position));
        bool pressed = pressedButtons.Contains(button);
        Color top = pressed ? Color.FromArgb(91, 221, 255) : (hovered ? Color.FromArgb(255, 239, 190) : Color.FromArgb(255, 225, 158));
        Color bottom = pressed ? Color.FromArgb(0, 157, 205) : (hovered ? Color.FromArgb(248, 163, 59) : Color.FromArgb(228, 139, 45));
        using (LinearGradientBrush brush = new LinearGradientBrush(r, top, bottom, LinearGradientMode.Vertical))
        using (Pen border = new Pen(Color.FromArgb(255, 230, 174), 2F))
        using (Pen glow = new Pen(Color.FromArgb(135, 255, 184, 88), 5F))
        using (SolidBrush ink = new SolidBrush(Color.FromArgb(30, 22, 11)))
        {
            g.DrawPath(glow, path);
            g.FillPath(brush, path);
            g.DrawPath(border, path);
            bool isSupport = Object.ReferenceEquals(button, supportButton);
            string label = isSupport ? "Support the creator\r\n(Dukung kreator)" : (finished ? "Done (Selesai)" : (installStarted ? "Installing (Menginstal)" : "Accept terms and install\r\n(Setujui & Instal)"));
            float fontSize = 10F;
            using (Font labelFont = new Font("Segoe UI Semibold", fontSize, FontStyle.Bold))
            using (StringFormat format = new StringFormat())
            {
                format.Alignment = StringAlignment.Center;
                format.LineAlignment = StringAlignment.Center;
                format.Trimming = StringTrimming.None;
                string[] lines = label.Split(new[] { "\r\n", "\n" }, StringSplitOptions.None);
                float lineHeight = labelFont.GetHeight(g);
                float firstLineY = (button.Height - lineHeight * lines.Length) / 2F;
                for (int i = 0; i < lines.Length; i++)
                {
                    RectangleF lineBounds = new RectangleF(4, firstLineY + i * lineHeight, button.Width - 8, lineHeight + 2F);
                    g.DrawString(lines[i], labelFont, ink, lineBounds, format);
                }
            }
        }
        }
    }

    private static void FitLabelToBounds(Label label)
    {
        if (label == null || label.Width <= 0 || label.Height <= 0 || String.IsNullOrEmpty(label.Text)) return;
        Font original = label.Font;
        float size = original.Size;
        TextFormatFlags flags = TextFormatFlags.WordBreak | TextFormatFlags.TextBoxControl;
        while (size > 7F)
        {
            using (Font candidate = new Font(original.FontFamily, size, original.Style))
            {
                Size measured = TextRenderer.MeasureText(label.Text, candidate, new Size(Math.Max(1, label.Width - 4), Int32.MaxValue), flags);
                if (measured.Height <= label.Height - 2) break;
            }
            size -= 0.5F;
        }
        if (size < original.Size) label.Font = new Font(original.FontFamily, size, original.Style);
    }

    private GraphicsPath RoundedPath(Rectangle r, float radius)
    {
        GraphicsPath path = new GraphicsPath();
        path.AddArc(r.X, r.Y, radius, radius, 180, 90);
        path.AddArc(r.Right - radius, r.Y, radius, radius, 270, 90);
        path.AddArc(r.Right - radius, r.Bottom - radius, radius, radius, 0, 90);
        path.AddArc(r.X, r.Bottom - radius, radius, radius, 90, 90);
        path.CloseFigure();
        return path;
    }

    private void DrawRoundedBorder(Graphics graphics, Rectangle rectangle, Color color, float width)
    {
        rectangle.Width -= 1;
        rectangle.Height -= 1;
        graphics.SmoothingMode = SmoothingMode.AntiAlias;
        using (GraphicsPath path = new GraphicsPath())
        using (Pen pen = new Pen(color, width))
        {
            int radius = 12;
            path.AddArc(rectangle.X, rectangle.Y, radius, radius, 180, 90);
            path.AddArc(rectangle.Right - radius, rectangle.Y, radius, radius, 270, 90);
            path.AddArc(rectangle.Right - radius, rectangle.Bottom - radius, radius, radius, 0, 90);
            path.AddArc(rectangle.X, rectangle.Bottom - radius, radius, radius, 90, 90);
            path.CloseFigure();
            graphics.DrawPath(pen, path);
        }
    }

    private void AddComponentDescription(string text, int x, int y, int width, int height)
    {
        Label description = new Label();
        description.Text = text;
        description.Location = new Point(x, y);
        description.Size = new Size(width, height);
        description.ForeColor = Color.FromArgb(151, 170, 189);
        description.Font = new Font("Segoe UI", 8F);
        componentsBox.Controls.Add(description);
    }

    private string GetDefaultInstallPath()
    {
        try
        {
            using (RegistryKey key = Registry.CurrentUser.OpenSubKey("Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\IndoSubMod"))
            {
                string installedApp = key == null ? null : key.GetValue("InstallLocation") as string;
                if (!String.IsNullOrWhiteSpace(installedApp) && Directory.Exists(Directory.GetParent(installedApp).FullName))
                    return Directory.GetParent(installedApp).FullName;
            }
        }
        catch { }
        return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "IndoSubMod");
    }

    private void BrowseForInstallPath()
    {
        if (installStarted) return;
        using (FolderBrowserDialog dialog = new FolderBrowserDialog())
        {
            dialog.Description = "Choose the IndoSubMod folder (Pilih folder IndoSubMod)";
            dialog.ShowNewFolderButton = true;
            if (Directory.Exists(installPathBox.Text)) dialog.SelectedPath = installPathBox.Text;
            if (dialog.ShowDialog(this) == DialogResult.OK) installPathBox.Text = dialog.SelectedPath;
        }
    }

    private void BeginInstall()
    {
        if (installStarted) return;
        if (!termsAccepted)
        {
            ShowInstallerDialog("Your consent is required (Persetujuan diperlukan)", "Click “Accept terms and install” to confirm that you accept the terms above. (Klik “Setujui & Instal” untuk menyatakan persetujuan.)", false);
            return;
        }
        try
        {
            installerPhase = "Checking the installation folder (Memeriksa folder instalasi)";
            string installRoot = Path.GetFullPath(installPathBox.Text.Trim());
            string driveRoot = Path.GetPathRoot(installRoot).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
            if (String.IsNullOrWhiteSpace(installPathBox.Text) || String.Equals(installRoot.TrimEnd(Path.DirectorySeparatorChar), driveRoot, StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("Choose a folder inside the drive, not the drive root. (Pilih folder di dalam drive, bukan root drive.)");
            installPathBox.Text = installRoot;
            installPathBox.ReadOnly = true;
            browseButton.Text = "Locked (Terkunci)";
            offlineModelBox.Enabled = false;
            desktopShortcutBox.Enabled = false;
            installStarted = true;
            overallStarted = DateTime.Now;
            operationStarted = overallStarted;
            displayedPercent = 0;
            lastReportedPercent = 0;
            progressReportBaseline = 0;
            lastProgressReportAt = overallStarted;
            progress.Value = 0;
            percentLabel.Text = "0.0%";
            progress.Style = ProgressBarStyle.Continuous;
            closeButton.Enabled = false;
            closeButton.Text = "Installing (Menginstal)";
            footerLabel.Text = "Keep this window open until setup is complete. (Jangan tutup jendela ini hingga instalasi selesai.)";
            string local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            logPath = Path.Combine(local, "IndoSubMod", "install.log");
            installerPhase = "Creating a temporary folder (Membuat folder sementara)";
            workDirectory = Path.Combine(Path.GetTempPath(), "IndoSubModSetup-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(workDirectory);
            stageLabel.Text = "Extracting components (Mengekstrak komponen)";
            installerPhase = "Extracting files from the EXE (Mengekstrak file dari EXE)";
            using (Stream resource = Assembly.GetExecutingAssembly().GetManifestResourceStream("IndoSubModPayload.zip"))
            {
                if (resource == null) throw new InvalidOperationException("The application files are missing from the installer. (File aplikasi tidak ditemukan di dalam pemasang.)");
                using (ZipArchive archive = new ZipArchive(resource, ZipArchiveMode.Read))
                {
                    archive.ExtractToDirectory(workDirectory);
                }
            }
            targetPercent = 2;
            stageLabel.Text = "Preparing setup (Menyiapkan instalasi)";
            installerPhase = "Starting Windows PowerShell (Memulai Windows PowerShell)";
            ProcessStartInfo info = new ProcessStartInfo();
            info.FileName = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), "WindowsPowerShell\\v1.0\\powershell.exe");
            string installRootArgument = Convert.ToBase64String(Encoding.Unicode.GetBytes(installRoot));
            // PowerShell's -File argument binder receives command-line values as strings.
            // The script validates and converts numeric 1/0 values explicitly.
            info.Arguments = "-NoLogo -NoProfile -ExecutionPolicy Bypass -File \"" + Path.Combine(workDirectory, "install.ps1") + "\" -InstallRootBase64 " + installRootArgument +
                " -InstallOfflineModel " + (offlineModelBox.Checked ? "1" : "0") +
                " -CreateDesktopShortcut " + (desktopShortcutBox.Checked ? "1" : "0");
            info.WorkingDirectory = workDirectory;
            info.UseShellExecute = false;
            info.CreateNoWindow = true;
            info.WindowStyle = ProcessWindowStyle.Hidden;
            info.RedirectStandardOutput = true;
            info.RedirectStandardError = true;
            info.StandardOutputEncoding = Encoding.UTF8;
            info.StandardErrorEncoding = Encoding.UTF8;
            child = new Process();
            child.StartInfo = info;
            child.EnableRaisingEvents = true;
            child.OutputDataReceived += OnOutput;
            child.ErrorDataReceived += OnError;
            child.Exited += OnExited;
            child.Start();
            child.BeginOutputReadLine();
            child.BeginErrorReadLine();
            targetPercent = 4;
            installerPhase = "Running the installation script (Menjalankan skrip instalasi)";
            stageLabel.Text = "Installing IndoSubMod (Menginstal IndoSubMod)";
        }
        catch (Exception ex)
        {
            FinishWithError(ex.ToString());
        }
    }

    private void OnOutput(object sender, DataReceivedEventArgs e)
    {
        if (e.Data == null) return;
        Match stageMatch = Regex.Match(e.Data, "IndoSubMod_STAGE\\|([a-z_]+)");
        if (stageMatch.Success)
        {
            string operation = StageDescription(stageMatch.Groups[1].Value);
            try
            {
                BeginInvoke((MethodInvoker)delegate
                {
                    currentOperation = operation;
                    operationStarted = DateTime.Now;
                    stageLabel.Text = operation;
                    FitLabelToBounds(stageLabel);
                    progress.Style = ProgressBarStyle.Continuous;
                    progress.MarqueeAnimationSpeed = 0;
                    UpdateActivityDetail();
                });
            }
            catch { }
            return;
        }
        Match match = Regex.Match(e.Data, "IndoSubMod_PROGRESS\\|(\\d{1,3})");
        if (!match.Success) return;
        int value;
        if (!Int32.TryParse(match.Groups[1].Value, out value)) return;
        try
        {
            BeginInvoke((MethodInvoker)delegate
            {
                lastReportedPercent = Math.Max(lastReportedPercent, Math.Min(100, value));
                targetPercent = lastReportedPercent;
                progressReportBaseline = lastReportedPercent;
                lastProgressReportAt = DateTime.Now;
                progress.Style = ProgressBarStyle.Continuous;
                progress.MarqueeAnimationSpeed = 0;
                operationStarted = DateTime.Now;
                UpdateStage(value);
                UpdateActivityDetail();
            });
        }
        catch { }
    }

    private void OnError(object sender, DataReceivedEventArgs e)
    {
        if (e.Data == null) return;
        lock (errors) { errors.AppendLine(e.Data); }
    }

    private void UpdateStage(int value)
    {
        if (value < 8) stageLabel.Text = "Preparing setup (Menyiapkan instalasi)";
        else if (value < 22) stageLabel.Text = "Preparing components (Menyiapkan komponen)";
        else if (value < 30) stageLabel.Text = "Configuring the environment (Menyiapkan lingkungan)";
        else if (value < 70) stageLabel.Text = "Installing libraries (Memasang pustaka)";
        else if (value < 78) stageLabel.Text = "Building the application (Menyusun aplikasi)";
        else if (value < 91) stageLabel.Text = "Preparing offline models (Menyiapkan model offline)";
        else if (value < 96) stageLabel.Text = "Updating IndoSubMod (Memperbarui IndoSubMod)";
        else if (value < 100) stageLabel.Text = "Registering with Windows (Mendaftarkan di Windows)";
        FitLabelToBounds(stageLabel);
    }

    private string StageDescription(string stage)
    {
        switch (stage)
        {
            case "python_download": return "Downloading Python (Mengunduh Python)";
            case "dependencies": return "Downloading and installing libraries (Mengunduh dan memasang pustaka)";
            case "build": return "Building IndoSubMod.exe (Menyusun IndoSubMod.exe)";
            case "models": return "Downloading speech and translation models (Mengunduh model ucapan dan terjemahan)";
            case "speech_model": return "Downloading the Whisper speech recognition model (Mengunduh model pengenalan ucapan Whisper)";
            case "replace": return "Replacing the installed IndoSubMod version (Mengganti versi IndoSubMod)";
            case "register": return "Adding IndoSubMod to the Windows app list (Menambahkan IndoSubMod ke daftar aplikasi Windows)";
            default: return "Installing (Menginstal)";
        }
    }

    private static string FormatDuration(TimeSpan value)
    {
        if (value.TotalSeconds < 0) value = TimeSpan.Zero;
        return value.TotalHours >= 1 ? value.ToString(@"h\:mm\:ss") : value.ToString(@"mm\:ss");
    }

    private void UpdateActivityDetail()
    {
        TimeSpan elapsed = overallStarted == DateTime.MinValue ? TimeSpan.Zero : DateTime.Now - overallStarted;
        string remaining = "estimate will appear during setup";
        string remainingId = "perkiraan muncul selama instalasi";
        if (displayedPercent >= 8 && displayedPercent < 99.5 && elapsed.TotalSeconds > 0)
        {
            TimeSpan eta = TimeSpan.FromSeconds(elapsed.TotalSeconds * (100 - displayedPercent) / Math.Max(0.1, displayedPercent));
            remaining = "about " + FormatDuration(eta);
            remainingId = "sekitar " + FormatDuration(eta);
        }
        detailLabel.Text = "Setup progress (estimated): " + displayedPercent.ToString("0.0") + "% • elapsed: " + FormatDuration(elapsed) + " • remaining: " + remaining + "\r\nProgres instalasi (perkiraan): " + displayedPercent.ToString("0.0") + "% • waktu: " + FormatDuration(elapsed) + " • tersisa: " + remainingId;
        FitLabelToBounds(detailLabel);
    }

    private void UpdateSmoothProgress()
    {
        if (!installStarted || finished || overallStarted == DateTime.MinValue) return;
        double elapsed = Math.Max(0, (DateTime.Now - overallStarted).TotalSeconds);
        double timeEstimate = 99.5 * (1.0 - Math.Exp(-elapsed / 300.0));
        double sinceReport = lastProgressReportAt == DateTime.MinValue ? 0 : Math.Max(0, (DateTime.Now - lastProgressReportAt).TotalSeconds);
        double phaseEstimate = progressReportBaseline + sinceReport * 0.35;
        double goal = Math.Min(99.5, Math.Max(timeEstimate, Math.Max(phaseEstimate, Math.Min(99.5, lastReportedPercent))));
        double gap = goal - displayedPercent;
        if (gap > 0)
        {
            double step = Math.Min(0.8, Math.Max(0.01, gap * 0.08));
            displayedPercent = Math.Min(goal, displayedPercent + step);
        }
        progress.Style = ProgressBarStyle.Continuous;
        progress.Value = Math.Max(0, Math.Min(progress.Maximum, (int)Math.Round(displayedPercent * 100.0)));
        percentLabel.Text = displayedPercent.ToString("0.0") + "%";
    }

    private void OnExited(object sender, EventArgs e)
    {
        try { BeginInvoke((MethodInvoker)delegate { CompleteInstall(); }); } catch { }
    }

    private void CompleteInstall()
    {
        if (child == null || child.ExitCode != 0)
        {
            string detail;
            lock (errors) { detail = errors.ToString(); }
            FinishWithError(String.IsNullOrWhiteSpace(detail) ? "Setup ended with an error.\r\n\r\nPemasang berhenti karena terjadi kesalahan." : detail);
            return;
        }
        finished = true;
        currentPercent = targetPercent = 100;
        displayedPercent = 100;
        lastReportedPercent = 100;
        progress.Style = ProgressBarStyle.Continuous;
        progress.Value = 10000;
        percentLabel.Text = "100%";
        stageLabel.Text = "Installation complete (Instalasi selesai)";
        detailLabel.Text = "IndoSubMod is installed and running.\r\nIndoSubMod telah terpasang dan berjalan.";
        footerLabel.Text = "Thank you for installing IndoSubMod. Use the button to support the creator.\r\nTerima kasih telah memasang IndoSubMod. Gunakan tombol untuk mendukung kreator.";
        FitLabelToBounds(stageLabel);
        FitLabelToBounds(detailLabel);
        FitLabelToBounds(footerLabel);
        supportButton.Visible = true;
        closeButton.Text = "Done (Selesai)";
        closeButton.Enabled = true;
        logButton.Enabled = true;
        CleanupTemp();
        animation.Stop();
    }

    private void FinishWithError(string detail)
    {
        finished = true;
        animation.Stop();
        string diagnostic = "Stage (Tahap): " + installerPhase + Environment.NewLine + "Details (Rincian): " + detail;
        RecordInstallerFailure(diagnostic);
        stageLabel.Text = "Setup could not be completed (Instalasi tidak dapat diselesaikan)";
        detailLabel.Text = "Error during this stage: " + installerPhase + "\r\nFull details are saved in the setup log.\r\nRincian lengkap tersimpan di log instalasi.";
        FitLabelToBounds(stageLabel);
        FitLabelToBounds(detailLabel);
        closeButton.Text = "Close (Tutup)";
        closeButton.Enabled = true;
        logButton.Enabled = File.Exists(logPath);
        string message = "IndoSubMod could not be installed. (IndoSubMod tidak dapat dipasang.)" + Environment.NewLine +
            "Stage (Tahap): " + installerPhase + Environment.NewLine + Environment.NewLine +
            "Log (Log): " + logPath + Environment.NewLine + Environment.NewLine + detail;
        ShowInstallerDialog("Installation error (Kesalahan instalasi)", message, true);
        CleanupTemp();
    }

    private void RecordInstallerFailure(string diagnostic)
    {
        try
        {
            if (String.IsNullOrWhiteSpace(logPath))
                logPath = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "IndoSubMod", "install.log");
            Directory.CreateDirectory(Path.GetDirectoryName(logPath));
            File.AppendAllText(logPath, Environment.NewLine + "=== IndoSubMod Setup diagnostic " + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + " ===" + Environment.NewLine + diagnostic + Environment.NewLine, Encoding.UTF8);
        }
        catch { }
    }

    private void OpenLog()
    {
        if (File.Exists(logPath))
        {
            Process.Start(new ProcessStartInfo("notepad.exe", "\"" + logPath + "\"") { UseShellExecute = false });
        }
        else
        {
            ShowInstallerDialog("Setup log (Log instalasi)", "The log has not been created yet. (Log belum dibuat.)", false);
        }
    }

    private void CleanupTemp()
    {
        try
        {
            if (!String.IsNullOrEmpty(workDirectory) && Directory.Exists(workDirectory))
                Directory.Delete(workDirectory, true);
        }
        catch { }
    }

    private void ShowInstallerDialog(string title, string message, bool isError)
    {
        using (Form dialog = new Form())
        using (Panel card = new Panel())
        using (Label heading = new Label())
        using (TextBox body = new TextBox())
        using (Button ok = new Button())
        {
            Color accent = isError ? Color.FromArgb(255, 126, 92) : cyan;
            dialog.Text = "IndoSubMod";
            dialog.Size = new Size(760, 430);
            dialog.MinimumSize = dialog.Size;
            dialog.MaximumSize = dialog.Size;
            dialog.StartPosition = FormStartPosition.CenterParent;
            dialog.FormBorderStyle = FormBorderStyle.FixedDialog;
            dialog.ShowInTaskbar = false;
            dialog.TopMost = true;
            dialog.BackColor = bg;
            dialog.ForeColor = Color.White;
            dialog.Font = Font;
            try { dialog.Icon = Icon; } catch { }
            card.Location = new Point(12, 12);
            card.Size = new Size(720, 380);
            card.BackColor = panel;
            heading.Text = "IndoSubMod  ✦  " + title;
            heading.Location = new Point(20, 18);
            heading.Size = new Size(680, 30);
            heading.ForeColor = accent;
            heading.Font = new Font("Segoe UI Semibold", 13F, FontStyle.Bold);
            body.Text = message;
            body.Location = new Point(20, 56);
            body.Size = new Size(680, 260);
            body.Multiline = true;
            body.ReadOnly = true;
            body.ScrollBars = ScrollBars.Vertical;
            body.BorderStyle = BorderStyle.FixedSingle;
            body.BackColor = bg;
            body.ForeColor = Color.FromArgb(220, 230, 240);
            body.Font = new Font("Segoe UI", 9F);
            body.WordWrap = true;
            ok.Text = "OK (Oke)";
            ok.Location = new Point(586, 326);
            ok.Size = new Size(112, 32);
            ok.FlatStyle = FlatStyle.Flat;
            ok.FlatAppearance.BorderSize = 0;
            ok.BackColor = cyan;
            ok.ForeColor = Color.FromArgb(3, 14, 25);
            AnimateButton(ok);
            ok.Click += delegate { dialog.Close(); };
            card.Controls.Add(heading);
            card.Controls.Add(body);
            card.Controls.Add(ok);
            dialog.Controls.Add(card);
            dialog.AcceptButton = ok;
            dialog.ShowDialog(this);
        }
    }

    protected override void OnFormClosed(FormClosedEventArgs e)
    {
        if (child != null && !child.HasExited)
        {
            try { child.Kill(); } catch { }
        }
        CleanupTemp();
        base.OnFormClosed(e);
    }
}

internal sealed class NeonProgressBar : Control
{
    private int minimum;
    private int maximum = 100;
    private int value;
    private ProgressBarStyle style = ProgressBarStyle.Continuous;
    private readonly Timer marqueeTimer = new Timer();
    private int marqueeOffset;
    private int marqueeDirection = 1;
    public Color GlowColor { get; set; }
    public int MarqueeAnimationSpeed
    {
        get { return style == ProgressBarStyle.Marquee ? 1000 / Math.Max(1, marqueeTimer.Interval) : 0; }
        set { marqueeTimer.Interval = Math.Max(16, Math.Min(1000, 1000 / Math.Max(1, value))); }
    }
    public int Minimum { get { return minimum; } set { minimum = value; Invalidate(); } }
    public int Maximum { get { return maximum; } set { maximum = Math.Max(value, minimum + 1); Invalidate(); } }
    public int Value { get { return value; } set { this.value = Math.Max(minimum, Math.Min(maximum, value)); Invalidate(); } }
    public ProgressBarStyle Style
    {
        get { return style; }
        set { style = value; if (style == ProgressBarStyle.Marquee) marqueeTimer.Start(); else marqueeTimer.Stop(); Invalidate(); }
    }

    public NeonProgressBar()
    {
        Height = 22;
        BackColor = Color.FromArgb(10, 23, 38);
        GlowColor = Color.FromArgb(0, 190, 255);
        SetStyle(ControlStyles.UserPaint | ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw, true);
        marqueeTimer.Interval = 45;
        marqueeTimer.Tick += delegate
        {
            int inner = Math.Max(1, Width - 18);
            int segment = Math.Max(65, Math.Min(145, inner / 3));
            int limit = Math.Max(0, inner - segment);
            marqueeOffset += 9 * marqueeDirection;
            if (marqueeOffset >= limit) { marqueeOffset = limit; marqueeDirection = -1; }
            else if (marqueeOffset <= 0) { marqueeOffset = 0; marqueeDirection = 1; }
            Invalidate();
        };
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        Graphics g = e.Graphics;
        g.SmoothingMode = SmoothingMode.AntiAlias;
        Rectangle outer = new Rectangle(2, 3, Math.Max(1, Width - 5), Math.Max(8, Height - 7));
        using (GraphicsPath path = new GraphicsPath())
        using (SolidBrush track = new SolidBrush(Color.FromArgb(13, 28, 42)))
        using (Pen border = new Pen(GlowColor, 1.5F))
        {
            AddRoundRect(path, outer, 10F);
            g.FillPath(track, path);
            g.DrawPath(border, path);
        }
        int innerWidth = Math.Max(0, outer.Width - 8);
        int fillWidth = style == ProgressBarStyle.Marquee ? Math.Min(145, innerWidth / 3) : (int)(innerWidth * (double)(value - minimum) / Math.Max(1, maximum - minimum));
        if (style == ProgressBarStyle.Marquee) fillWidth = Math.Max(65, fillWidth);
        if (fillWidth <= 0) return;
        int left = outer.Left + 4;
        if (style == ProgressBarStyle.Marquee) left += Math.Min(Math.Max(0, innerWidth - fillWidth), marqueeOffset);
        Rectangle fill = new Rectangle(left, outer.Top + 4, Math.Min(fillWidth, Math.Max(1, outer.Right - left - 4)), Math.Max(2, outer.Height - 8));
        using (GraphicsPath fillPath = new GraphicsPath())
        using (LinearGradientBrush fillBrush = new LinearGradientBrush(fill, Color.FromArgb(0, 220, 255), Color.FromArgb(0, 111, 221), LinearGradientMode.Vertical))
        using (Pen glow = new Pen(Color.FromArgb(110, GlowColor), 4F))
        {
            AddRoundRect(fillPath, fill, 8F);
            g.DrawPath(glow, fillPath);
            g.FillPath(fillBrush, fillPath);
        }
    }

    private static void AddRoundRect(GraphicsPath path, Rectangle r, float radius)
    {
        path.AddArc(r.X, r.Y, radius, radius, 180, 90);
        path.AddArc(r.Right - radius, r.Y, radius, radius, 270, 90);
        path.AddArc(r.Right - radius, r.Bottom - radius, radius, radius, 0, 90);
        path.AddArc(r.X, r.Bottom - radius, radius, radius, 90, 90);
        path.CloseFigure();
    }
}

internal static class IndoSubModSetup
{
    [STAThread]
    private static void Main()
    {
        SetProcessDPIAware();
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        try { Application.Run(new InstallerForm()); }
        catch (Exception ex)
        {
            MessageBox.Show(ex.ToString(), "IndoSubMod Setup — Startup error (Kesalahan awal)", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    [DllImport("user32.dll")]
    private static extern bool SetProcessDPIAware();
}

