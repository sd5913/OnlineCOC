using System;
using System.IO;
using System.IO.Compression;
using System.Diagnostics;
using System.Drawing;
using System.Reflection;
using System.Security.Cryptography;
using System.Threading.Tasks;
using System.Windows.Forms;

internal static class Setup {
    static readonly string Probe = "import sys,ssl,asyncio,importlib.metadata as m; import aiohttp,aiortc,av,argon2,cryptography,pylibsrtp; from onlinecoc_web.host import WebHost; from onlinecoc_web.portal import WebDirectory; from onlinecoc_p2p.client import Player; import json,pathlib; p=pathlib.Path(sys.executable).parent.parent/'dependency-versions.json'; assert all(m.version(k)==v for k,v in json.loads(p.read_text()).items()); from aiortc import RTCPeerConnection";
    static string Root(string value) {
        string root = Path.GetFullPath(value.Trim()).TrimEnd(Path.DirectorySeparatorChar);
        foreach (string part in new [] {"engineering/network-p2p/pyproject.toml", "engineering/network-web/pyproject.toml", "engineering/network-web/src/onlinecoc_web/__init__.py"})
            if (!File.Exists(Path.Combine(root, part))) throw new Exception("请选择包含 engineering 的 OnlineCOC 项目根目录。");
        RejectLinks(root);
        return root;
    }
    static void RejectLinks(string path) {
        var directory = new DirectoryInfo(path);
        while (directory != null) {
            if (directory.Exists && (directory.Attributes & FileAttributes.ReparsePoint) != 0)
                throw new Exception("安装目录不能使用符号链接或目录联接：" + directory.FullName);
            directory = directory.Parent;
        }
    }
    static void Check(string runtime) {
        string code = Probe;
        code += "; p=RTCPeerConnection(); asyncio.run(p.close()); print('Network runtime OK')";
        var info = new ProcessStartInfo(Path.Combine(runtime, "Scripts/python.exe"), "-B -c \"" + code + "\"");
        info.UseShellExecute = false; info.CreateNoWindow = true;
        info.RedirectStandardOutput = true; info.RedirectStandardError = true;
        info.EnvironmentVariables["PYTHONUTF8"] = "1";
        info.EnvironmentVariables.Remove("PYTHONHOME"); info.EnvironmentVariables.Remove("PYTHONPATH");
        using (var process = Process.Start(info)) {
            var stdout = process.StandardOutput.ReadToEndAsync(); var stderr = process.StandardError.ReadToEndAsync();
            if (!process.WaitForExit(60000)) { process.Kill(); throw new Exception("依赖自检超时。"); }
            Task.WaitAll(stdout, stderr);
            if (process.ExitCode != 0) throw new Exception("依赖自检失败：\r\n" + stderr.Result);
        }
    }
    static void Install(string selected, Action<string> log) {
        string root = Root(selected);
        string parent = Path.GetFullPath(Path.Combine(root,"engineering/network-p2p"));
        RejectLinks(parent);
        string target = Path.Combine(parent,".venv"); RejectLinks(target);
        string stamp = DateTime.Now.ToString("yyyyMMdd-HHmmss") + "-" + Guid.NewGuid().ToString("N").Substring(0,8);
        string stage = Path.Combine(parent,".network-setup-" + stamp);
        string backup = Path.Combine(parent,"local/runtime-backups/" + stamp);
        RejectLinks(Path.GetDirectoryName(backup));
        using (var guard = new FileStream(Path.Combine(parent,".network-setup.lock"),FileMode.OpenOrCreate,FileAccess.ReadWrite,FileShare.None)) {
            log("正在校验离线安装包…");
            using (var input = Assembly.GetExecutingAssembly().GetManifestResourceStream("runtime.zip"))
            using (var sha = SHA256.Create()) {
                string hash = BitConverter.ToString(sha.ComputeHash(input)).Replace("-", "").ToLowerInvariant();
                if (hash != PayloadHash.Value) throw new Exception("安装包损坏，请重新获取 EXE。");
            }
            Directory.CreateDirectory(stage);
            using (var input = Assembly.GetExecutingAssembly().GetManifestResourceStream("runtime.zip"))
            using (var zip = new ZipArchive(input,ZipArchiveMode.Read)) {
                foreach (var entry in zip.Entries) {
                    string path = Path.GetFullPath(Path.Combine(stage, entry.FullName));
                    if (!path.StartsWith(stage + Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase)) throw new Exception("安装包路径无效。");
                    Directory.CreateDirectory(Path.GetDirectoryName(path));
                    if (entry.Name.Length > 0) using (var source=entry.Open()) using (var output=File.Create(path)) source.CopyTo(output);
                }
            }
            log("正在自检 Python、WebRTC、加密与联机模块…"); Check(stage);
            bool backed = false, installed = false;
            try {
                if (Directory.Exists(target)) {
                    // Never move a junction or an active Python runtime. Renaming loaded DLLs fails safely.
                    foreach (var process in Process.GetProcesses()) using (process) {
                        try {
                            string file=process.MainModule.FileName;
                            if (file.StartsWith(target + Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase))
                                throw new InvalidOperationException("请先关闭正在使用该联机环境的程序，再安装。");
                        } catch (System.ComponentModel.Win32Exception) {} catch (InvalidOperationException e) {
                            if (e.Message.StartsWith("请先")) throw;
                        }
                    }
                    Directory.CreateDirectory(Path.GetDirectoryName(backup));
                    Directory.Move(target,backup); backed=true;
                }
                Directory.Move(stage,target); installed=true;
                Check(target);
                File.WriteAllText(Path.Combine(target,"onlinecoc-network-runtime.txt"),"Offline dependency runtime 1.0.0\r\nPython 3.14.2 x64\r\n");
                log("安装完成。可启动项目的网页联机或 P2P 入口。" + (backed ? "\r\n原环境已保留："+backup : ""));
            } catch {
                if (installed && Directory.Exists(target)) Directory.Move(target,stage);
                if (backed) Directory.Move(backup,target);
                throw;
            }
        }
    }
    [STAThread] static int Main(string[] args) {
        if (args.Length == 2 && (args[0] == "--install" || args[0] == "--verify")) {
            try {
                Console.SetOut(new StreamWriter(Console.OpenStandardOutput(), new System.Text.UTF8Encoding(false)) { AutoFlush = true });
                Console.SetError(new StreamWriter(Console.OpenStandardError(), new System.Text.UTF8Encoding(false)) { AutoFlush = true });
                string root=Root(args[1]);
                if (args[0]=="--install") Install(root, delegate(string value) { Console.WriteLine(value); });
                else Check(Path.Combine(root,"engineering/network-p2p/.venv"));
                return 0;
            } catch (Exception e) { Console.Error.WriteLine(e.Message); return 1; }
        }
        Application.EnableVisualStyles(); Application.SetCompatibleTextRenderingDefault(false);
        var form = new Form {Text="OnlineCOC 联机依赖安装",ClientSize=new Size(720,360),StartPosition=FormStartPosition.CenterScreen,Font=new Font("Microsoft YaHei UI",10)};
        var label=new Label {Text="选择已复制的 OnlineCOC 项目目录，然后一键安装。\r\n离线安装 Python 与联机依赖；不修改账号、证书、存档或系统 PATH。",Left=20,Top=20,Width=680,Height=56};
        var path=new TextBox {Left=20,Top=86,Width=570};
        var browse=new Button {Text="选择目录",Left=600,Top=82,Width=100,Height=34};
        var start=new Button {Text="一键安装",Left=20,Top=132,Width=150,Height=40};
        var status=new TextBox {Left=20,Top=190,Width=680,Height=145,Multiline=true,ReadOnly=true,ScrollBars=ScrollBars.Vertical,Text="适用 Windows 10/11 x64。纯浏览器玩家无需安装。\r\n仅安装联机依赖；游戏宿主和配置包依赖由项目另行准备。"};
        var ancestor=new DirectoryInfo(AppDomain.CurrentDomain.BaseDirectory);
        while(ancestor!=null) { if(File.Exists(Path.Combine(ancestor.FullName,"engineering/network-web/pyproject.toml"))) {path.Text=ancestor.FullName;break;} ancestor=ancestor.Parent; }
        browse.Click+=delegate {using(var dialog=new FolderBrowserDialog()){dialog.Description="选择 OnlineCOC 项目根目录";if(dialog.ShowDialog()==DialogResult.OK)path.Text=dialog.SelectedPath;}};
        bool busy=false;
        form.FormClosing+=(sender,e)=>{if(busy)e.Cancel=true;};
        start.Click+=async delegate {
            busy=true;start.Enabled=browse.Enabled=path.Enabled=false;
            string selected=path.Text;
            try {await Task.Run(()=>Install(selected,message=>form.Invoke((Action)(()=>status.Text=message))));}
            catch(Exception e){status.Text="安装失败："+e.Message+"\r\n原有配置与存档未改动，可关闭相关程序后重试。";}
            finally{busy=false;start.Enabled=browse.Enabled=path.Enabled=true;}
        };
        form.Controls.AddRange(new Control[]{label,path,browse,start,status});Application.Run(form);return 0;
    }
}
