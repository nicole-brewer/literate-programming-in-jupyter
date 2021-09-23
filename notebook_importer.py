import sys
sys.path

sys.meta_path

import importlib
from IPython import get_ipython
import nbformat
import os, sys
from IPython.core.interactiveshell import InteractiveShell

class NotebookLoader(importlib.abc.InspectLoader, importlib.abc.MetaPathFinder):
    '''An abstract base class for a loader which implements the optional
    PEP 302 protocol for loaders that inspect modules.
    
    Parameters:
        path: path to the directory containing the module [string]
        module_name: a name to use for the module. Path basename is default [string]
        remove_magics: remove all cell and line magics from Notebook cell source code
    '''
    def __init__(self, module_path, remove_magics=True):
        self.remove_magics = remove_magics
        self.shell = InteractiveShell.instance()
        self.module_path = os.path.expanduser(module_path)  
        if not os.path.isdir(self.module_path):
            raise FileNotFoundError('Module directory %s not found.' % self.module_path)
        self.module_name = [dirname for dirname in self.module_path.split('/') if dirname != ''][-1]

    def get_filename(self, fullname):
        '''An abstract method that is to return the value of __file__ for the specified module.
        If no path is available, ImportError is raised. If source code is available, then the 
        method should return the path to the source file
        '''
        parts = fullname.split('.')
        if parts[0] != self.module_name:
            raise ImportError('Module %s doesn\'t exist' % parts[0])
        if len(parts) == 1:
            nb_path = 'this file does not exist'
            init_path = '__init__.py'
        elif len(parts) == 2:
            nb_path = parts[1] + '.ipynb'
            init_path = os.path.join(parts[1], '__init__.py')
        else:
            parts[-1] = parts[-1] + '.ipynb'
            nb_path = os.path.join(parts[1], *parts[2:])
            init_path = os.path.join(parts[1], *parts[2:], '__init__.py')
            
        for path in (nb_path, init_path):
            fullpath = os.path.join(self.module_path, path)
            if os.path.exists(fullpath):
                return fullpath
        raise ImportError('Module %s does not exist at %s' % (fullname, fullpath))
            
        
    def get_code(self, fullname):
        '''Return the code object for a module, or None if the module does not have a code
        object (as would be the case, for example, for a built-in module). Raise an 
        ImportError if loader cannot find the requested module.
        '''
        filename = self.get_filename(fullname)
        return self.get_code_from_file(filename)

    def get_source(self, fullname):
        '''An abstract method to return the source of a module. It is returned as a
        text string using universal newlines, translating all recognized line separators
        into '\n' characters. Returns None if no source is available (e.g. a built-in module).
        Raises ImportError if the loader cannot find the module specified.
        '''
        return self.get_code(fullname)
       
    def get_code_from_file(self, filename):
        if self.is_nb(filename):
            return self.get_nb_source(filename)
        else:
            return self.get_init_source(filename)
        
            
    def get_init_source(self, filename):
        with open(filename, 'r') as f:
            return f.read()
        raise ModuleNotFoundError('Filename %s not readable' % filename)
        
    def get_nb_source(self, filename):
        try:
            nb = nbformat.read(filename, as_version=4)
            code_cells = [c for c in nb['cells'] if c['cell_type'] == 'code']
            nb_source = ''
            for code_cell in code_cells:
                if self.remove_magics:
                    nb_source += self.remove_all_magics(code_cell.source) + '\n'
                else: # turn magics into executable code
                    nb_source += self.shell.input_transformer_manager.transform_cell(code_cell.source)
            return nb_source
        except:
            raise ModuleNotFoundExpection('Notebook %s not readable' % filename)

    def remove_all_magics(self, string):
        ret = ''
        if string.startswith('%%'):
            return ret
        for line in string.splitlines():
            if not line.lstrip().startswith('%'):
                ret += line + '\n'
        return ret
    
    def is_nb(self, filename):
        return filename.endswith('.ipynb')

    def is_package(self, fullname):
        '''An abstract method to return a true value if the module is a package, a false
        value otherwise. ImportError is raised if the loader cannot find the module.
        '''
        return fullname == self.module_name
    
    def exec_module(self, module):
        '''An abstract method that executes the module in its own namespace when a module 
        is imported or reloaded. The module should already be initialized when exec_module() 
        is called. When this method exists, create_module() must be defined.
        '''
        try:
            exec(self.get_code_from_file(module.__file__), module.__dict__)
        except:
            print('Error executing %s' % module.__file__)
            print(self.get_code_from_file(module.__file__))
            raise

class NotebookFinder(importlib.abc.MetaPathFinder):
    
    def __init__(self, module_path):
        self.module_path = module_path

    def find_spec(self, fullname, path, target=None):
        '''An abstract method for finding a spec for the specified module. If this
        is a top-level import, path will be None. Otherwise, this is a search for
        a subpackage or module and path will be the value of __path__ from the parent
        package. If a spec cannot be found, None is returned. When passed in, target
        is a module object that the finder may use to make a more educated guess about
        what spec to return. importlib.util.spec_from_loader() may be useful for 
        implementing concrete MetaPathFinders.
        '''
        loader = NotebookLoader(self.module_path) # __loader__: The Loader that should be used when loading the module. Finders should always set this.
        name = fullname # __name__: A string for the fully-qualified name of the module.
        # __cached__: String for where the compiled module should be stored (or None).
        # __package__: (Read-only) The fully-qualified name of the package under which the module should be loaded as a submodule (or the empty string for top-level modules). For packages, it is the same as __name__.
        location = loader.get_filename(fullname) # __file__: The path to where the module data is stored (not set for built-in modules).
        self.submodule_search_locations = None # __path__: List of strings for where to find submodules, if a package (None otherwise).
        if not location.endswith('.ipynb'):
            (spec_dir, _) = os.path.split(location)
            self.submodule_search_locations = []
            self.submodule_search(spec_dir)
        spec = importlib.util.spec_from_file_location(name, location, loader=loader, submodule_search_locations=self.submodule_search_locations)
        return spec
    
    def submodule_search(self, location):
        locations = [os.path.join(location, f) for f in os.listdir(location) if not f.startswith('.')]
        locations = [d for d in locations if os.path.isdir(d) and os.path.isfile(os.path.join(d, '__init__.py'))]
        self.submodule_search_locations = locations

sys.meta_path.append(NotebookFinder('nbs'))

print(sys.meta_path)


from nbs.module import hello_world

hello_world()

from nbs.another_module import conversation

conversation()


from nbs.child.baby_module import babble

babble()

import os, sys
import nbformat
from IPython import get_ipython

def remove_all_magics(string):
    ret = ''
    if string.startswith('%%'):
        return ret
    for line in string.splitlines():
        if not line.lstrip().startswith('%'):
            ret += line + '\n'
    return ret

def is_nb(filename):
    return filename.endswith('.ipynb')

def get_nb_source(filename, remove_magics=True):
    assert is_nb(filename), 'File %s is not a Jupyter notebook' % filename
    try:
        nb = nbformat.read(filename, as_version=4)
        code_cells = [c for c in nb['cells'] if c['cell_type'] == 'code']
        nb_source = ''
        for code_cell in code_cells:
            if remove_magics:
                nb_source += remove_all_magics(code_cell.source) + '\n'
            else: # turn magics into executable code
                nb_source += shell.input_transformer_manager.transform_cell(code_cell.source)
        return nb_source
    except:
        raise Exception('Notebook %s not readable' % filename)

def nb_to_py(nbFile, pyPath=None, overwrite=False, remove_magics=True):
    nbFile = os.path.expanduser(nbFile)
    dirname, basename = os.path.split(nbFile)
    if pyPath:
        dirname = os.path.expanduser(pyPath)
    basename = basename.split('.')[0] + '.py'
    pyFile = os.path.join(dirname, basename)
    if not overwrite:
        assert not os.path.exists(pyFile), 'File at %s already exists. Use argument overwrite=True to overwrite' % pyFile
    source = get_nb_source(nbFile, remove_magics)
    with open(pyFile, "w") as pyFile:
        pyFile.write(source)

def nbs_to_pkg(nbDir, pyDir=None, remove_magics=True):
    nbDir = os.path.expanduser(nbDir)
    packageName = [dirname for dirname in nbDir.split('/') if dirname != ''][-1]
    if pyDir:
        pyDir = os.path.expanduser(pyDir)
    else: 
        pyDir = nbDir
    recurse(nbDir, pyDir, '', remove_magics)
    
def recurse(nbDir, pyDir, currentDir, remove_magics):
    nbPath = os.path.join(nbDir, currentDir)
    pyPath = os.path.join(pyDir, currentDir)
    nbs = [child for child in os.listdir(nbPath) if not child.startswith('.') and child.endswith('.ipynb') and child != 'application.ipynb']
    for nb in nbs:
        nbFile = os.path.join(nbPath, nb)
        os.makedirs(pyPath, exist_ok=True) 
        nb_to_py(nbFile, pyPath, overwrite=True)
        
    initFile = os.path.join(pyDir, '__init__.py')
    with open(initFile, 'w') as f:
        pass
        
    childDirs = [child for child in os.listdir(nbPath) if not child.startswith('.') and not child.startswith('__')]
    childDirs = [child for child in childDirs if os.path.isdir(os.path.join(nbPath, child))]
    if childDirs:
        for childDir in childDirs:
            newCurrent = os.path.join(currentDir, childDir)
            recurse(nbDir, pyDir, newCurrent, remove_magics)

@magics_class
class NotebookWriter(Magics):
    
    shell = get_ipython()
    
    @cell_magic
    @magic_arguments.magic_arguments()
    @magic_arguments.argument('--verbose', '-v',
          help='Whether to omit cell from being written into python file.'
    )
    def omit(self, line='', cell=None):
        args = magic_arguments.parse_argstring(self.omit, line)
        self.shell.run_cell(cell)
        
    @line_magic
    @magic_arguments.magic_arguments()
    @magic_arguments.argument('--verbose', '-v',
        help='Clear output and save the current notebook and write it to python.')
    @magic_arguments.argument('notebook')
    @magic_arguments.argument('--pyPath', '-d', default=os.getcwd())
    @magic_arguments.argument('--nbPath', '-s', default=os.getcwd())
    @magic_arguments.argument('--overwrite', '-f', default=False)
    def nb_to_py(self, line='', cell=None):
        args = magic_arguments.parse_argstring(self.nb_to_py, line)
        nbFile = os.path.join(args.nbPath, args.notebook)
        assert os.path.isfile(nbFile), 'Notebook not found at %s' % nbFile
        assert os.path.isdir(args.pyPath), '%s is not an existing directory' % agrs.pyPath
        nb_to_py(nbFile=nbFile, pyPath=args.pyPath, overwrite=args.overwrite)

here = Path('.').resolve()
nbs = here / 'nbs'
pkg  = here / 'pkg'
nbs_to_pkg(nbs/pkg)


from IPython.core import magic_arguments
from IPython.core.magic import line_magic, cell_magic, line_cell_magic, Magics, magics_class
from IPython import get_ipython
import os

@magics_class
class NotebookWriter(Magics):
    
    shell = get_ipython()
    
    @cell_magic
    @magic_arguments.magic_arguments()
    @magic_arguments.argument('--verbose', '-v',
          help='Whether to omit cell from being written into python file.'
    )
    def omit(self, line='', cell=None):
        args = magic_arguments.parse_argstring(self.omit, line)
        self.shell.run_cell(cell)
        
    @line_magic
    @magic_arguments.magic_arguments()
    @magic_arguments.argument('--verbose', '-v',
        help='Clear output and save the current notebook and write it to python.')
    @magic_arguments.argument('notebook')
    @magic_arguments.argument('--pyPath', '-d', default=os.getcwd())
    @magic_arguments.argument('--nbPath', '-s', default=os.getcwd())
    @magic_arguments.argument('--overwrite', '-f', default=False)
    def nb_to_py(self, line='', cell=None):
        args = magic_arguments.parse_argstring(self.nb_to_py, line)
        nbFile = os.path.join(args.nbPath, args.notebook)
        assert os.path.isfile(nbFile), 'Notebook not found at %s' % nbFile
        assert os.path.isdir(args.pyPath), '%s is not an existing directory' % agrs.pyPath
        nb_to_py(nbFile=nbFile, pyPath=args.pyPath, overwrite=args.overwrite)

shell = get_ipython()
shell.register_magics(NotebookWriter)



