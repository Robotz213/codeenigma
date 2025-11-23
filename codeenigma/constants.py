import platform

EXTENSION_COMPILED_MODULE = ".so" if platform.system() != "Windows" else ".pyd"
