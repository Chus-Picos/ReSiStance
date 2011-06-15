#!/usr/bin/env python
# -*- coding: utf-8 -*-

#########################################################################
#    Copyright (C) 2010 Sergio Villar Senin <svillar@igalia.com>
#
#    This file is part of ReSiStance
#
#    ReSiStance is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    ReSiStance is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with ReSiStance.  If not, see <http://www.gnu.org/licenses/>.
#########################################################################

try:
    from sugar.activity import bundlebuilder
    bundlebuilder.start()
except ImportError:
    import sys
    sys.path = ['src'] + sys.path
    import glob
    import os
    from distutils.core import setup
    from distutils import cmd
    from distutils.command.install import install as _install
    from distutils.command.install_data import install_data as _install_data
    from distutils.command.build import build as _build
    from ReSiStance import constants
    import msgfmt
    
    # Thanks to Deluge project for all the build stuff
    class write_data_install_path(cmd.Command):
        description = 'saves the data installation path for access at runtime'
    
        def initialize_options(self):
            self.prefix = None
            self.lib_build_dir = None
    
        def finalize_options(self):
            self.set_undefined_options('install',
                ('prefix', 'prefix')
            )
            self.set_undefined_options('build',
                ('build_lib', 'lib_build_dir')
            )
    
        def run(self):
            pass

    class unwrite_data_install_path(cmd.Command):
        description = 'undoes write_data_install_path'
    
        def initialize_options(self):
            self.lib_build_dir = None
    
        def finalize_options(self):
            self.set_undefined_options('build',
                ('build_lib', 'lib_build_dir')
            )
    
        def run(self):
            pass

    class build_trans(cmd.Command):
        description = 'Compile .po files into .mo files'
    
        def initialize_options(self):
            pass

        def finalize_options(self):
            pass

        def run(self):
            po_dir = os.path.join(os.path.dirname(os.curdir), 'po')
            for path, names, filenames in os.walk(po_dir):
                for f in filenames:
                    if f.endswith('.po'):
                        lang = f[:len(f) - 3]
                        src = os.path.join(path, f)
                        dest_path = os.path.join('build', 'locale', lang, 'LC_MESSAGES')
                        dest = os.path.join(dest_path, 'resistance.mo')
                        if not os.path.exists(dest_path):
                            os.makedirs(dest_path)
                        if not os.path.exists(dest):
                            print 'Compiling %s' % src
                            msgfmt.make(src, dest)
                        else:
                            src_mtime = os.stat(src)[8]
                            dest_mtime = os.stat(dest)[8]
                            if src_mtime > dest_mtime:
                                print 'Compiling %s' % src
                                msgfmt.make(src, dest)
    
    class build(_build):
        sub_commands = _build.sub_commands + [('build_trans', None)]
        def run(self):
            _build.run(self)
    
    class install(_install):
        sub_commands = [('write_data_install_path', None)] + \
            _install.sub_commands + [('unwrite_data_install_path', None)]
        def run(self):
            _install.run(self)
    
    class install_data(_install_data):
        def run(self):
            for lang in os.listdir('build/locale/'):
                lang_dir = os.path.join('share', 'locale', lang, 'LC_MESSAGES')
                lang_file = os.path.join('build', 'locale', lang, 'LC_MESSAGES', 'resistance.mo')
                self.data_files.append( (lang_dir, [lang_file]) )
            _install_data.run(self)
    
    cmdclass = {
        'build': build,
        'build_trans': build_trans,
        'install_data': install_data,
        'write_data_install_path': write_data_install_path,
        'unwrite_data_install_path': unwrite_data_install_path,
    }

    try: 
        import hildon    
        setup(name = constants.RSS_NAME.lower(),
             version = constants.RSS_VERSION,
             description = constants.RSS_DESCRIPTION,
             author = 'Sergio Villar Senín',
             author_email = 'svillar@igalia.com',
             url = constants.RSS_URL,
             license = 'GPL v3',
             packages = ['ReSiStance'],
             package_dir = {'': 'src'},
             scripts = ['resistance'],
             data_files = [('share/icons/hicolor/scalable/apps',['data/resistance.png']
                          ),
                          ('share/applications/hildon', ['data/resistance.desktop']
                          ),
                          ('share/resistance', ['data/resistance_spec.ini']
                          ),
                          ('share/resistance', ['data/feed-presence.png']
                          ),
                          ('share/resistance', ['data/prism-google-reader.png']
                          ),
                          ('share/resistance', ['data/export.png']
                          ),
                          ('share/resistance', ['data/import.png']
                          ),
                          ('share/resistance', ['data/prism-google-reader_remove.png']
                          ),
                          ('share/resistance', ['data/add-to-label.png', 'data/remove-from-label.png']
                          )
                          ],
             cmdclass=cmdclass
            )
    except ImportError:
        setup(name = constants.RSS_NAME.lower(),
             version = constants.RSS_VERSION,
             description = constants.RSS_DESCRIPTION,
             author = 'Sergio Villar Senín',
             author_email = 'svillar@igalia.com',
             url = constants.RSS_URL,
             license = 'GPL v3',
             packages = ['ReSiStance'],
             package_dir = {'': 'src'},
             scripts = ['resistance'],
             data_files = [('share/icons/hicolor/scalable/apps',['data/resistance.png']
                          ),
                          ('share/applications', ['data/resistance.desktop']
                          ),
                          ('share/resistance', ['data/resistance_spec.ini']
                          ),
                          ('share/resistance', ['data/feed-presence.png']
                          ),
                          ('share/resistance', ['data/prism-google-reader.png']
                          ),
                          ('share/resistance', ['data/export.png']
                          ),
                          ('share/resistance', ['data/import.png']
                          ),
                          ('share/resistance', ['data/prism-google-reader_remove.png']
                          ),
                          ('share/resistance', ['data/add-to-label.png', 'data/remove-from-label.png']
                          )
                          ],
             cmdclass=cmdclass
            )
    
