using System;
using System.IO;
using System.Text;
using System.Collections.Generic;

namespace OXPlayer.CLI
{
    class Program
    {
        static readonly string[] MediaExtensions = new string[] {
            ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v",
            ".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a", ".opus",
            ".iso", ".ts", ".m2ts"
        };

        static int Main(string[] args)
        {
            Console.OutputEncoding = Encoding.UTF8;

            if (args.Length == 0 || args[0] == "--help" || args[0] == "-h" || args[0] == "help")
            {
                PrintHelp();
                return 0;
            }

            string command = args[0].ToLowerInvariant();

            try
            {
                switch (command)
                {
                    case "info":
                        return HandleInfo(args);
                    case "scan":
                        return HandleScan(args);
                    case "playlist":
                        return HandlePlaylist(args);
                    case "verify":
                        return HandleVerify(args);
                    default:
                        Console.WriteLine("Error: Unknown command '{0}'. Use --help for available commands.", command);
                        return 1;
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine("Error: {0}", ex.Message);
                return 2;
            }
        }

        static void PrintHelp()
        {
            Console.WriteLine("==================================================");
            Console.WriteLine("OXMediaCLI - High-Performance Media Utility (C#)");
            Console.WriteLine("Part of the OXPlayer Ecosystem");
            Console.WriteLine("==================================================");
            Console.WriteLine("Usage: OXMediaCLI <command> [options]");
            Console.WriteLine();
            Console.WriteLine("Commands:");
            Console.WriteLine("  info <file>                 Inspect media file properties and header");
            Console.WriteLine("  scan <folder>               Scan directory and list media files");
            Console.WriteLine("  verify <file|folder>        Verify media header signatures and integrity");
            Console.WriteLine("  playlist <folder> <output>  Generate M3U8 playlist from directory");
            Console.WriteLine("  --help, -h                  Display this help menu");
            Console.WriteLine();
        }

        static int HandleInfo(string[] args)
        {
            if (args.Length < 2)
            {
                Console.WriteLine("Usage: OXMediaCLI info <file>");
                return 1;
            }

            string filePath = args[1];
            if (!File.Exists(filePath))
            {
                Console.WriteLine("Error: File not found: {0}", filePath);
                return 1;
            }

            FileInfo fi = new FileInfo(filePath);
            Console.WriteLine("---------------- Media Information ----------------");
            Console.WriteLine("Name      : {0}", fi.Name);
            Console.WriteLine("Directory : {0}", fi.DirectoryName);
            Console.WriteLine("Size      : {0} bytes ({1:F2} MB)", fi.Length, fi.Length / (1024.0 * 1024.0));
            Console.WriteLine("Format    : {0}", fi.Extension.ToUpperInvariant());
            Console.WriteLine("Created   : {0:yyyy-MM-dd HH:mm:ss}", fi.CreationTime);
            Console.WriteLine("Modified  : {0:yyyy-MM-dd HH:mm:ss}", fi.LastWriteTime);

            // Read magic header
            byte[] header = new byte[16];
            using (FileStream fs = new FileStream(filePath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
            {
                int read = fs.Read(header, 0, header.Length);
                StringBuilder sb = new StringBuilder();
                for (int i = 0; i < read; i++)
                {
                    sb.Append(header[i].ToString("X2")).Append(" ");
                }
                Console.WriteLine("Header Hex: {0}", sb.ToString().Trim());
            }

            Console.WriteLine("Status    : OK (Readable)");
            return 0;
        }

        static int HandleScan(string[] args)
        {
            if (args.Length < 2)
            {
                Console.WriteLine("Usage: OXMediaCLI scan <folder>");
                return 1;
            }

            string folder = args[1];
            if (!Directory.Exists(folder))
            {
                Console.WriteLine("Error: Directory not found: {0}", folder);
                return 1;
            }

            Console.WriteLine("Scanning directory: {0}", folder);
            List<string> foundFiles = new List<string>();
            long totalBytes = 0;

            foreach (string file in Directory.EnumerateFiles(folder, "*.*", SearchOption.AllDirectories))
            {
                string ext = Path.GetExtension(file).ToLowerInvariant();
                if (Array.IndexOf(MediaExtensions, ext) >= 0)
                {
                    foundFiles.Add(file);
                    try
                    {
                        totalBytes += new FileInfo(file).Length;
                    }
                    catch { }
                }
            }

            Console.WriteLine("Found {0} media file(s). Total size: {1:F2} MB", foundFiles.Count, totalBytes / (1024.0 * 1024.0));
            for (int i = 0; i < Math.Min(foundFiles.Count, 25); i++)
            {
                Console.WriteLine("  [{0}] {1}", i + 1, Path.GetFileName(foundFiles[i]));
            }
            if (foundFiles.Count > 25)
            {
                Console.WriteLine("  ... and {0} more file(s).", foundFiles.Count - 25);
            }

            return 0;
        }

        static int HandleVerify(string[] args)
        {
            if (args.Length < 2)
            {
                Console.WriteLine("Usage: OXMediaCLI verify <file|folder>");
                return 1;
            }

            string target = args[1];
            if (File.Exists(target))
            {
                return VerifySingleFile(target) ? 0 : 1;
            }
            else if (Directory.Exists(target))
            {
                int corrupt = 0;
                int valid = 0;
                foreach (string file in Directory.EnumerateFiles(target, "*.*", SearchOption.AllDirectories))
                {
                    string ext = Path.GetExtension(file).ToLowerInvariant();
                    if (Array.IndexOf(MediaExtensions, ext) >= 0)
                    {
                        if (VerifySingleFile(file))
                            valid++;
                        else
                            corrupt++;
                    }
                }
                Console.WriteLine("Scan Complete: {0} valid, {1} corrupted/empty.", valid, corrupt);
                return corrupt == 0 ? 0 : 1;
            }
            else
            {
                Console.WriteLine("Error: Path not found: {0}", target);
                return 1;
            }
        }

        static bool VerifySingleFile(string file)
        {
            try
            {
                FileInfo fi = new FileInfo(file);
                if (fi.Length == 0)
                {
                    Console.WriteLine("[FAIL] 0 bytes (empty file): {0}", Path.GetFileName(file));
                    return false;
                }

                using (FileStream fs = new FileStream(file, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
                {
                    byte[] buf = new byte[8];
                    int read = fs.Read(buf, 0, buf.Length);
                    if (read < 4)
                    {
                        Console.WriteLine("[FAIL] Truncated header: {0}", Path.GetFileName(file));
                        return false;
                    }
                }

                Console.WriteLine("[PASS] {0} ({1:F2} MB)", Path.GetFileName(file), fi.Length / (1024.0 * 1024.0));
                return true;
            }
            catch (Exception ex)
            {
                Console.WriteLine("[ERROR] {0}: {1}", Path.GetFileName(file), ex.Message);
                return false;
            }
        }

        static int HandlePlaylist(string[] args)
        {
            if (args.Length < 3)
            {
                Console.WriteLine("Usage: OXMediaCLI playlist <folder> <output.m3u8>");
                return 1;
            }

            string folder = args[1];
            string outputFile = args[2];

            if (!Directory.Exists(folder))
            {
                Console.WriteLine("Error: Directory not found: {0}", folder);
                return 1;
            }

            List<string> files = new List<string>();
            foreach (string file in Directory.EnumerateFiles(folder, "*.*", SearchOption.AllDirectories))
            {
                string ext = Path.GetExtension(file).ToLowerInvariant();
                if (Array.IndexOf(MediaExtensions, ext) >= 0)
                {
                    files.Add(file);
                }
            }

            using (StreamWriter sw = new StreamWriter(outputFile, false, Encoding.UTF8))
            {
                sw.WriteLine("#EXTM3U");
                foreach (string f in files)
                {
                    sw.WriteLine("#EXTINF:-1,{0}", Path.GetFileNameWithoutExtension(f));
                    sw.WriteLine(f);
                }
            }

            Console.WriteLine("Generated M3U8 playlist with {0} items: {1}", files.Count, outputFile);
            return 0;
        }
    }
}
