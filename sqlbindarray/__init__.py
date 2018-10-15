# Make so that importing this package is the same as importing the sqlbindarray
# module within it (i.e. make the package behave like a module to importers).
# See sqlbindarray.py for documentation.
from .sqlbindarray import *
__doc__ = sqlbindarray.__doc__
