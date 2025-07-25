import gzip
import os
import shutil
import subprocess
import sys
import requests

CUSTOM_NAME = "ajeossida"

# Temporarily fixing the issue 'Failed to reach single-threaded state', Process.enumerateThreads() crash
TEMP = 0


def run_command(command, cwd=None):
    try:
        result = subprocess.run(command, shell=True, cwd=cwd, check=True, text=True)
        return result.returncode
    except subprocess.CalledProcessError as e:
        print(f"Error while running command: {command}\nError: {e}")
        sys.exit(1)


def git_clone_repo():
    repo_url = "https://github.com/frida/frida.git"
    destination_dir = os.path.join(os.getcwd(), "ajeossida")

    print(f"\n[*] Cloning repository {repo_url} to {destination_dir}...")
    run_command(f"git clone --recurse-submodules {repo_url} {destination_dir}")


def download_ndk():
    url = "https://dl.google.com/android/repository/android-ndk-r25c-linux.zip"
    file_name = "android-ndk-r25c-linux.zip"
    unzip_dir = "android-ndk-r25c"

    if not os.path.exists(unzip_dir):
        if not os.path.exists(file_name):
            print(f"\n[*] Downloading {file_name}...")
            response = requests.get(url, stream=True)
            with open(file_name, 'wb') as file:
                for chunk in response.iter_content(chunk_size=128):
                    file.write(chunk)
            print(f"\n[*] Downloaded {file_name}")

        run_command(f"unzip {file_name} >/dev/null")

    #os.remove(file_name)

    return unzip_dir


def configure_build(ndk_path, arch):

    build_dir = os.path.join(os.getcwd(), "ajeossida", arch)
    if os.path.exists(build_dir):
        return build_dir
    os.makedirs(build_dir, exist_ok=True)
    os.environ['ANDROID_NDK_ROOT'] = ndk_path

    result = run_command(f"{os.path.join('..', 'configure')} --host={arch}", cwd=build_dir)

    if result == 0:
        return build_dir
    else:
        print("\n[!] Failed to configure")
        sys.exit(1)


def build(build_dir):
    run_command("make", cwd=build_dir)


def replace_strings_in_files(directory, search_string, replace_string):
    if os.path.isfile(directory):
        file_path = directory
        with open(file_path, 'r+', encoding='utf-8') as file:
            content = file.read()
            if search_string in content:
                print(f"Patch {file.name}")
                patched_content = content.replace(search_string, replace_string)
                file.seek(0)
                file.write(patched_content)
                file.truncate()
    else:
        for root, dirs, files in os.walk(directory):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                try:
                    with open(file_path, 'r+', encoding='utf-8') as file:
                        content = file.read()
                        if search_string in content:
                            print(f"Patch {file.name}")
                            patched_content = content.replace(search_string, replace_string)
                            file.seek(0)
                            file.write(patched_content)
                            file.truncate()
                except Exception as e:
                    pass


def compress_file(file_path):
    try:
        # Create a .gz file from the original file
        with open(file_path, 'rb') as f_in:
            with gzip.open(file_path + '.gz', 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        print(f"[*] Compressed {file_path} to {file_path}.gz")
    except Exception as e:
        print(f"[!] Error compressing {file_path}: {e}")


def capitalize_first_lower_char(word):
    for index, char in enumerate(word):
        if char.islower():
            # Replace the first lowercase character with its uppercase equivalent
            return word[:index] + char.upper() + word[index + 1:]
    return word


def fix_failed_to_reach_single_threaded_state(custom_dir):
    old_cloak_vala_path = os.path.join(custom_dir, "subprojects/frida-core/lib/payload/cloak.vala")
    new_cloak_vala_path = os.path.join(os.getcwd(), "fix_failed_to_reach_single_threaded_state.txt")
    os.remove(old_cloak_vala_path)
    shutil.copy(new_cloak_vala_path, old_cloak_vala_path)


def fix_process_enumerate_threads_crash(custom_dir):
    # On the Pixel 4a, if there is a thread named perfetto_hprof_, Process.enumerateThreads() crashes with SEGV_ACCERR
    gumprocess_linux_path = os.path.join(custom_dir, "subprojects/frida-gum/gum/backend-linux/gumprocess-linux.c")
    replace_strings_in_files(gumprocess_linux_path,
                             '    details.name = thread_name;',
                             '    details.name = thread_name;\n'
                             '    if (strcmp(details.name, "perfetto_hprof_") == 0)\n'
                             '        continue;')


def main():
    global CUSTOM_NAME
    if os.getenv("CUSTOM_NAME"):
        CUSTOM_NAME = os.getenv("CUSTOM_NAME")
    custom_dir = os.path.join(os.getcwd(), "ajeossida")
    #if os.path.exists(custom_dir):
    #    print(f"\n[*] Cleaning {custom_dir}...")
    #    shutil.rmtree(custom_dir)

    assets_dir = os.path.join(os.getcwd(), "assets")
    if os.path.exists(assets_dir):
        print(f"\n[*] Cleaning {assets_dir}...")
        shutil.rmtree(assets_dir)
    os.mkdir(assets_dir)
    is_frist = False

    if not os.path.exists(custom_dir):
        is_frist = True
        if os.path.exists("../frida.zip"):
            run_command(f"unzip -q ../frida.zip -d {custom_dir}")
        else:
            git_clone_repo()
        CUSTOM_VERSION = os.getenv("CUSTOM_VERSION")
        if CUSTOM_VERSION:
            run_command("git checkout " + CUSTOM_VERSION, cwd=custom_dir)
            run_command("git submodule update --init --recursive --force", cwd=custom_dir)
    if os.path.exists("../deps.zip"):
        run_command(f"unzip -q ../deps.zip -d {custom_dir}")

    ndk_path = os.path.join(os.getcwd(), download_ndk())

    architectures = ["android-arm64", "android-arm", "android-x86_64", "android-x86"]
    #architectures = ["android-arm64"]
    if TEMP == 1:
        architectures = ["android-arm64"]
    build_dirs = [configure_build(ndk_path, arch) for arch in architectures]

    if is_frist:

        # libfrida-agent-raw.so patch
        print(f"\n[*] Patch 'libfrida-agent-raw.so' with 'lib{CUSTOM_NAME}-agent-raw.so' recursively...")
        patch_string = "libfrida-agent-raw.so"
        replace_strings_in_files(custom_dir,
                                patch_string,
                                patch_string.replace("frida", CUSTOM_NAME))

        # re.frida.server patch
        print(f"\n[*] Patch 're.frida.server' with 're.{CUSTOM_NAME}.server' recursively...")
        patch_string = "re.frida.server"
        replace_strings_in_files(custom_dir,
                                patch_string,
                                patch_string.replace("frida", CUSTOM_NAME))

        # frida-helper patch
        print(f"\n[*] Patch 'frida-helper' with '{CUSTOM_NAME}-helper' recursively...")
        patch_strings = ["frida-helper-32", "frida-helper-64", "get_frida_helper_", "\"/frida-\""]
        for patch_string in patch_strings:
            replace_strings_in_files(custom_dir,
                                    patch_string,
                                    patch_string.replace("frida", CUSTOM_NAME))

        # frida-agent patch
        print(f"\n[*] Patch 'frida-agent' with '{CUSTOM_NAME}-agent' recursively...")
        patch_strings = ["frida-agent-", "\"agent\" / \"frida-agent.", "\'frida-agent\'", "\"frida-agent\"",
                        "get_frida_agent_", "\'FridaAgent\'"]
        for patch_string in patch_strings:
            replace_strings_in_files(custom_dir,
                                    patch_string,
                                    patch_string.replace("Frida", capitalize_first_lower_char(
                                        CUSTOM_NAME)) if "Frida" in patch_string else
                                    patch_string.replace("frida", CUSTOM_NAME))

        # Patch the original file back, which has incorrectly patched strings.
        wrong_patch_strings = [f'{CUSTOM_NAME}-agent-x86.symbols', f'{CUSTOM_NAME}-agent-android.version']
        for wrong_patch_string in wrong_patch_strings:
            replace_strings_in_files(custom_dir,
                                    wrong_patch_string,
                                    wrong_patch_string.replace(CUSTOM_NAME, 'frida'))

        # memfd_create patch, memfd:ajeossida-agent-64.so --> memfd:jit-cache
        print(f"\n[*] Patch MemoryFileDescriptor.memfd_create")
        frida_helper_backend_path = os.path.join(custom_dir,
                                                "subprojects/frida-core/src/linux/frida-helper-backend.vala")
        replace_strings_in_files(frida_helper_backend_path,
                                'return Linux.syscall (SysCall.memfd_create, name, flags);',
                                'return Linux.syscall (SysCall.memfd_create, \"jit-cache\", flags);')

        # frida-server patch
        print(f"\n[*] Patch 'frida-server' with '{CUSTOM_NAME}-server' recursively...")
        frida_server_meson_path = os.path.join(custom_dir, "subprojects/frida-core/server/meson.build")
        patch_strings = ["frida-server-raw", "\'frida-server\'", "\"frida-server\"", "frida-server-universal"]
        for patch_string in patch_strings:
            replace_strings_in_files(frida_server_meson_path,
                                    patch_string,
                                    patch_string.replace("frida", CUSTOM_NAME))

        frida_core_compat_build_path = os.path.join(custom_dir, "subprojects/frida-core/compat/build.py")
        patch_string = "frida-server"
        replace_strings_in_files(frida_core_compat_build_path,
                                patch_string,
                                patch_string.replace("frida", CUSTOM_NAME))

        # frida-gadget patch
        print(f"\n[*] Patch 'frida-gadget' with '{CUSTOM_NAME}-gadget' recursively...")
        patch_strings = ["\"frida-gadget\"", "\"frida-gadget-tcp", "\"frida-gadget-unix"]
        for patch_string in patch_strings:
            replace_strings_in_files(custom_dir,
                                    patch_string,
                                    patch_string.replace("frida", CUSTOM_NAME))

        frida_core_meson_path = os.path.join(custom_dir, "subprojects/frida-core/meson.build")
        patch_string = "gadget_name = 'frida-gadget' + shlib_suffix"
        replace_strings_in_files(frida_core_meson_path,
                                patch_string,
                                patch_string.replace("frida", CUSTOM_NAME))

        frida_core_compat_build_py_path = os.path.join(custom_dir, "subprojects/frida-core/compat/build.py")
        patch_string = "frida-gadget"
        replace_strings_in_files(frida_core_compat_build_py_path,
                                patch_string,
                                patch_string.replace("frida", CUSTOM_NAME))

        frida_gadget_meson_path = os.path.join(custom_dir, "subprojects/frida-core/lib/gadget/meson.build")
        patch_strings = ["frida-gadget-modulated", "libfrida-gadget-modulated", "frida-gadget-raw", "\'frida-gadget\'",
                        "frida-gadget-universal", "FridaGadget.dylib"]
        for patch_string in patch_strings:
            replace_strings_in_files(frida_gadget_meson_path,
                                    patch_string,
                                    patch_string.replace("Frida", capitalize_first_lower_char(
                                        CUSTOM_NAME)) if "Frida" in patch_string else
                                    patch_string.replace("frida", CUSTOM_NAME))

        # gum-js-loop patch
        print(f"\n[*] Patch 'gum-js-loop' with '{CUSTOM_NAME}-js-loop' recursively...")
        patch_string = "\"gum-js-loop\""
        replace_strings_in_files(custom_dir,
                                patch_string,
                                patch_string.replace("gum", CUSTOM_NAME))

        # pool-frida patch
        print(f"\n[*] Patch 'pool-frida' with 'pool-{CUSTOM_NAME}' recursively...")
        patch_string = "g_set_prgname (\"frida\");"
        replace_strings_in_files(custom_dir,
                                patch_string,
                                patch_string.replace("frida", CUSTOM_NAME))

        """ # No libc.so libsystem_c.dylib hooking
        print(f"\n[*] Patch not to hook libc function")
        # frida/subprojects/frida-core/lib/payload/exit-monitor.vala
        exit_monitor_path = os.path.join(custom_dir, "subprojects/frida-core/lib/payload/exit-monitor.vala")
        patch_string = "interceptor.attach"
        replace_strings_in_files(exit_monitor_path,
                                patch_string,
                                "// " + patch_string)

        # frida/subprojects/frida-gum/gum/backend-posix/gumexceptor-posix.c
        gumexceptor_posix_path = os.path.join(custom_dir, "subprojects/frida-gum/gum/backend-posix/gumexceptor-posix.c")
        gumexceptor_posix_patch_strings = ["gum_interceptor_replace",
                                        "gum_exceptor_backend_replacement_signal, self, NULL);",
                                        "gum_exceptor_backend_replacement_sigaction, self, NULL);"]
        for patch_string in gumexceptor_posix_patch_strings:
            replace_strings_in_files(gumexceptor_posix_path,
                                    patch_string,
                                    "// " + patch_string) """

        # hook patch nop 
        print(f"\n[*] Patch guminterceptor-arm64")
        run_command(f"patch -p0 < guminterceptor-arm64.patch")
        
        # 修改STRUCT 返回错误
        print(f"\n[*] Patch ggumquickcore.c")
        run_command(f"patch -p0 < gumquickcore.c.patch")
        
        
        # Selinux patch for Android
        print(f"\n[*] Patch 'frida_file', 'frida_memfd with '{CUSTOM_NAME}_file', '{CUSTOM_NAME}_memfd recursively...")
        patch_strings = ["\"frida_file\"", "\"frida_memfd\"", ":frida_file", ":frida_memfd"]
        for patch_string in patch_strings:
            replace_strings_in_files(custom_dir,
                                    patch_string,
                                    patch_string.replace("frida", CUSTOM_NAME))

        # Perform the first build
        for build_dir in build_dirs:
            print(f"\n[*] First build for {build_dir.rsplit('/')[-1]}")
            build(build_dir)

        # frida_agent_main patch
        print(f"\n[*] Patch 'frida_agent_main' with '{CUSTOM_NAME}_agent_main' recursively...")
        patch_string = "frida_agent_main"
        replace_strings_in_files(custom_dir,
                                patch_string,
                                patch_string.replace("frida", CUSTOM_NAME))

        if TEMP == 1:
            fix_failed_to_reach_single_threaded_state(custom_dir)
            fix_process_enumerate_threads_crash(custom_dir)

    # Second build after patching
    for build_dir in build_dirs:
        print(f"\n[*] Second build for {build_dir.rsplit('/')[-1]}")
        build(build_dir)

    # Patch gmain, gdbus, pool-spawner
    gmain = bytes.fromhex('67 6d 61 69 6e 00')
    amain = bytes.fromhex('61 6d 61 69 6e 00')

    gdbus = bytes.fromhex('67 64 62 75 73 00')
    gdbug = bytes.fromhex('67 64 62 75 67 00')

    pool_spawner = bytes.fromhex('70 6f 6f 6c 2d 73 70 61 77 6e 65 72 00')
    pool_spoiler = bytes.fromhex('70 6f 6f 6c 2d 73 70 6f 69 6c 65 72 00')

    patch_list = [os.path.join(build_dir, f"subprojects/frida-core/server/{CUSTOM_NAME}-server") for build_dir in build_dirs] + \
                 [os.path.join(build_dir, f"subprojects/frida-core/lib/agent/{CUSTOM_NAME}-agent.so") for build_dir in build_dirs] + \
                 [os.path.join(build_dir, f"subprojects/frida-core/lib/gadget/{CUSTOM_NAME}-gadget.so") for build_dir in build_dirs]

    for file_path in patch_list:
        # Open the binary file for reading and writing
        with open(file_path, 'rb+') as f:
            print(f"\n[*] gmain, gdbus, pool-spawner patch for {file_path}")
            # Read the entire file content
            content = f.read()
            patched_content = content.replace(gmain, amain)
            patched_content = patched_content.replace(gdbus, gdbug)
            patched_content = patched_content.replace(pool_spawner, pool_spoiler)

            f.seek(0)
            f.write(patched_content)
            f.truncate()

    # Get frida version
    frida_version_py = os.path.join(custom_dir, "releng/frida_version.py")
    result = subprocess.run(['python3', frida_version_py], capture_output=True, text=True)
    frida_version = result.stdout.strip()
    os.environ["ver_name"] = frida_version
    # Rename
    for file_path in patch_list:
        if '-agent.so' in file_path:
            continue

        arch = [i for i in file_path.split(os.sep) if i.startswith('android-')]
        arch = arch[0] if arch else ''

        if file_path.endswith('.so'):
            new_file_path = f"{file_path.rsplit('.so', 1)[0]}-{frida_version}-{arch}.so"
            if TEMP == 1:
                new_file_path = f"{file_path.rsplit('.so', 1)[0]}-{frida_version}-{arch}-temp.so"
        else:
            new_file_path = f"{file_path}-{frida_version}-{arch}"
            if TEMP == 1:
                new_file_path = f"{file_path}-{frida_version}-{arch}-temp"

        try:
            os.rename(file_path, new_file_path)
            print(f"\n[*] Renamed {file_path} to {new_file_path}")
            compress_file(new_file_path)

            shutil.move(f"{new_file_path}.gz", f"{assets_dir}")
        except Exception as e:
            print(f"[!] Error renaming {file_path}: {e}")


if __name__ == "__main__":
    main()
