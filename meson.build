project('rencher', version: '1.3.0')

name = 'Rencher'
app_id = 'com.github.danatationn.rencher'
description = 'Play and mod Ren\'Py games'

pkgdata_dir = join_paths(
	get_option('prefix'),
	get_option('datadir'),
	meson.project_name()
)

python = import('python')
python_install = python.find_installation()
gnome = import('gnome')

# conf
conf = configuration_data()
conf.set('name', name)
conf.set('project_name', meson.project_name())
conf.set('version', meson.project_version())
conf.set('copyright', '© 2026 danatationn')
conf.set('app_id', app_id)
conf.set('pkgdata_dir', pkgdata_dir)
conf.set('description', description)
conf.set('bin_dir', join_paths(get_option('prefix'), get_option('bindir')))
conf.set('python_dir', join_paths(get_option('prefix'), python_install.get_install_dir()))
if host_machine.system() == 'windows'
    conf.set('venv_dir', meson.current_source_dir() / '.venv/Lib/site-packages')
else
    conf.set('venv_dir', meson.current_source_dir() / '.venv/lib/python3.14/site-packages')
endif
freeze_dir = run_command(
    python_install, '-c',
    'import sysconfig; print(f"exe.{sysconfig.get_platform()}-{sysconfig.get_python_version()}")',
    check: true,
).stdout().strip()
conf.set('build_dir', meson.project_build_root() / freeze_dir)

message(conf.get('build_dir'))

# install
subdir('rencher')
subdir('data')
subdir('bin')
install_subdir(meson.project_name(), install_dir: python_install.get_install_dir())
if host_machine.system() == 'linux'
    gnome.post_install(
    	gtk_update_icon_cache: true,
    	update_desktop_database: true,
    )
endif

# freeze
if host_machine.system() == 'windows'
    nsi = configure_file(
        input: 'build_installer.nsi.in',
        output: 'build_installer.nsi',
        configuration: conf
    )

    run_target('freeze', command: ['freeze.py', get_option('prefix'), meson.project_build_root()])
    run_target('makensis', command: ['makensis', nsi])
endif
