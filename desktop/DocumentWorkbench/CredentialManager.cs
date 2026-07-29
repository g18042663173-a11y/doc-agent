using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Text;

namespace DocumentWorkbench;

public static class CredentialManager
{
    public const string NgaCredentialTarget = "HuaweiDocumentGenerator/NGA";

    public static string? ReadNgaToken() => Read(NgaCredentialTarget);

    public static void WriteNgaToken(string token)
    {
        if (string.IsNullOrWhiteSpace(token) || token.Length > 1280)
        {
            throw new ArgumentException("NGA Token 长度无效。", nameof(token));
        }
        Write(NgaCredentialTarget, token);
    }

    public static void DeleteNgaToken() => Delete(NgaCredentialTarget);

    private static string? Read(string target)
    {
        if (!CredRead(target, 1, 0, out var pointer))
        {
            var error = Marshal.GetLastWin32Error();
            if (error == 1168)
            {
                return null;
            }
            throw new Win32Exception(error, "无法读取 Windows 凭据。 ");
        }
        try
        {
            var credential = Marshal.PtrToStructure<NativeCredential>(pointer);
            if (credential.CredentialBlob == IntPtr.Zero || credential.CredentialBlobSize == 0)
            {
                return null;
            }
            var bytes = new byte[credential.CredentialBlobSize];
            Marshal.Copy(credential.CredentialBlob, bytes, 0, bytes.Length);
            return Encoding.Unicode.GetString(bytes);
        }
        finally
        {
            CredFree(pointer);
        }
    }

    private static void Write(string target, string secret)
    {
        var bytes = Encoding.Unicode.GetBytes(secret);
        var blob = Marshal.AllocCoTaskMem(bytes.Length);
        try
        {
            Marshal.Copy(bytes, 0, blob, bytes.Length);
            var credential = new NativeCredential
            {
                Type = 1,
                TargetName = target,
                CredentialBlobSize = (uint)bytes.Length,
                CredentialBlob = blob,
                Persist = 2,
                UserName = Environment.UserName,
            };
            if (!CredWrite(ref credential, 0))
            {
                throw new Win32Exception(Marshal.GetLastWin32Error(), "无法写入 Windows 凭据。");
            }
        }
        finally
        {
            var zero = new byte[bytes.Length];
            Marshal.Copy(zero, 0, blob, zero.Length);
            Marshal.FreeCoTaskMem(blob);
        }
    }

    private static void Delete(string target)
    {
        if (CredDelete(target, 1, 0))
        {
            return;
        }
        var error = Marshal.GetLastWin32Error();
        if (error != 1168)
        {
            throw new Win32Exception(error, "无法删除 Windows 凭据。");
        }
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct NativeCredential
    {
        public uint Flags;
        public uint Type;
        public string TargetName;
        public string? Comment;
        public System.Runtime.InteropServices.ComTypes.FILETIME LastWritten;
        public uint CredentialBlobSize;
        public IntPtr CredentialBlob;
        public uint Persist;
        public uint AttributeCount;
        public IntPtr Attributes;
        public string? TargetAlias;
        public string UserName;
    }

    [DllImport("advapi32.dll", EntryPoint = "CredReadW", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool CredRead(string target, uint type, uint reservedFlag, out IntPtr credentialPtr);

    [DllImport("advapi32.dll", EntryPoint = "CredWriteW", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool CredWrite([In] ref NativeCredential credential, uint flags);

    [DllImport("advapi32.dll", EntryPoint = "CredDeleteW", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool CredDelete(string target, uint type, uint flags);

    [DllImport("advapi32.dll", SetLastError = false)]
    private static extern void CredFree(IntPtr buffer);
}
