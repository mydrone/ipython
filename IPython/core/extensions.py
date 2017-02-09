# encoding: utf-8
"""A class for managing IPython extensions."""

# Copyright (c) IPython Development Team.
# Distributed under the terms of the Modified BSD License.

import os
import os.path
import warnings
import textwrap
from shutil import copyfile
import sys
from importlib import import_module

from traitlets.config.configurable import Configurable
from IPython.utils.path import ensure_dir_exists
from traitlets import Instance

try:
    from importlib import reload
except ImportError :
    ## deprecated since 3.4
    from imp import reload

#-----------------------------------------------------------------------------
# Main class
#-----------------------------------------------------------------------------

class ExtensionManager(Configurable):
    """A class to manage IPython extensions.

    An IPython extension is an importable Python module that has
    a function with the signature::

        def load_ipython_extension(ipython):
            # Do things with ipython

    This function is called after your extension is imported and the
    currently active :class:`InteractiveShell` instance is passed as
    the only argument.  You can do anything you want with IPython at
    that point, including defining new magic and aliases, adding new
    components, etc.
    
    You can also optionally define an :func:`unload_ipython_extension(ipython)`
    function, which will be called if the user unloads or reloads the extension.
    The extension manager will only call :func:`load_ipython_extension` again
    if the extension is reloaded.

    You can put your extension modules anywhere you want, as long as
    they can be imported by Python's standard import mechanism.  However,
    to make it easy to write extensions, you can also put your extensions
    in ``os.path.join(self.ipython_dir, 'extensions')``.  This directory
    is added to ``sys.path`` automatically.
    """

    shell = Instance('IPython.core.interactiveshell.InteractiveShellABC', allow_none=True)

    def __init__(self, shell=None, **kwargs):
        super(ExtensionManager, self).__init__(shell=shell, **kwargs)
        self.shell.observe(
            self._on_ipython_dir_changed, names=('ipython_dir',)
        )
        self.loaded = set()

    @property
    def ipython_extension_dir(self):
        return os.path.join(self.shell.ipython_dir, u'extensions')

    def _on_ipython_dir_changed(self, change):
        ensure_dir_exists(self.ipython_extension_dir)

    def load_extension(self, module_str):
        """Load an IPython extension by its module name.

        Returns the string "already loaded" if the extension is already loaded,
        "no load function" if the module doesn't have a load_ipython_extension
        function, or None if it succeeded.
        """
        if module_str in self.loaded:
            return "already loaded"

        from IPython.utils.syspathcontext import prepended_to_syspath

        with self.shell.builtin_trap:
            if module_str not in sys.modules:
                with prepended_to_syspath(self.ipython_extension_dir):
                    mod = import_module(module_str)
                    if mod.__file__.startswith(self.ipython_extension_dir):
                        print(textwrap.dedent(
                        """
                        Warning, you are attempting to load and IPython extensions from legacy
                        location.
                            
                        IPythonhas been requested to load extension `{ext}` which has been found in
                        `ipython_extension_dir` (`{dir}`).

                        It is likely you previously installed an extension using the `%install_ext`
                        mechanism which has been deprecated since IPython 4.0. Loading extensions
                        from the above directory is still supported but will be deprecated in a
                        future version of IPython.

                        Extensions should now be installed and managed as Python packages. We
                        recommend you update your extensions accordingly.

                        Old extensions files present in `ipython_extension_dir` may cause newly
                        installed extensions to not be recognized. Thus you may need to clean
                        the content of above mentioned directory.
                        """.format(dir=self.ipython_extension_dir, ext=module_str)))
            mod = sys.modules[module_str]
            if self._call_load_ipython_extension(mod):
                self.loaded.add(module_str)
            else:
                return "no load function"

    def unload_extension(self, module_str):
        """Unload an IPython extension by its module name.

        This function looks up the extension's name in ``sys.modules`` and
        simply calls ``mod.unload_ipython_extension(self)``.
        
        Returns the string "no unload function" if the extension doesn't define
        a function to unload itself, "not loaded" if the extension isn't loaded,
        otherwise None.
        """
        if module_str not in self.loaded:
            return "not loaded"
        
        if module_str in sys.modules:
            mod = sys.modules[module_str]
            if self._call_unload_ipython_extension(mod):
                self.loaded.discard(module_str)
            else:
                return "no unload function"

    def reload_extension(self, module_str):
        """Reload an IPython extension by calling reload.

        If the module has not been loaded before,
        :meth:`InteractiveShell.load_extension` is called. Otherwise
        :func:`reload` is called and then the :func:`load_ipython_extension`
        function of the module, if it exists is called.
        """
        from IPython.utils.syspathcontext import prepended_to_syspath

        if (module_str in self.loaded) and (module_str in sys.modules):
            self.unload_extension(module_str)
            mod = sys.modules[module_str]
            with prepended_to_syspath(self.ipython_extension_dir):
                reload(mod)
            if self._call_load_ipython_extension(mod):
                self.loaded.add(module_str)
        else:
            self.load_extension(module_str)

    def _call_load_ipython_extension(self, mod):
        if hasattr(mod, 'load_ipython_extension'):
            mod.load_ipython_extension(self.shell)
            return True

    def _call_unload_ipython_extension(self, mod):
        if hasattr(mod, 'unload_ipython_extension'):
            mod.unload_ipython_extension(self.shell)
            return True

    def install_extension(self, url, filename=None):
        """Download and install an IPython extension. 

        If filename is given, the file will be so named (inside the extension
        directory). Otherwise, the name from the URL will be used. The file must
        have a .py or .zip extension; otherwise, a ValueError will be raised.

        Returns the full path to the installed file.
        """
        # Ensure the extension directory exists
        ensure_dir_exists(self.ipython_extension_dir)

        if os.path.isfile(url):
            src_filename = os.path.basename(url)
            copy = copyfile
        else:
            # Deferred imports
            from urllib.parse import urlparse
            from urllib.request import urlretrieve
            src_filename = urlparse(url).path.split('/')[-1]
            copy = urlretrieve

        if filename is None:
            filename = src_filename
        if os.path.splitext(filename)[1] not in ('.py', '.zip'):
            raise ValueError("The file must have a .py or .zip extension", filename)

        filename = os.path.join(self.ipython_extension_dir, filename)
        copy(url, filename)
        return filename


