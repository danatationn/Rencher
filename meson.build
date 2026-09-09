project('rencher', version: '1.3.0')

name = 'Rencher'
app_id = 'com.github.danatationn.rencher'
description = 'Play and mod Ren\'Py games'

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
conf.set('pkgdata_dir', get_option('prefix') / get_option('datadir') / meson.project_name())
conf.set('description', description)
conf.set('bin_dir', get_option('prefix') / get_option('bindir'))
conf.set('python_dir', get_option('prefix') / python_install.get_install_dir())
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

# install
configure_file(
	input: meson.project_name() + '.in',
	output: meson.project_name(),
	configuration: conf,
	install_dir: get_option('bindir'),
	install_mode: 'rwxr-xr-x'
)
run_target('run', command: [meson.project_build_root() / meson.project_name()])
run_target('dev', command: [meson.project_build_root() / meson.project_name(), '--verbose'])
run_target('ver', command: [meson.project_build_root() / meson.project_name(), '--version'])

subdir('data')
# subdir('po')

install_subdir(meson.project_name(), install_dir: python_install.get_install_dir())
install_subdir(name + '.egg-info', install_dir: python_install.get_install_dir())
if host_machine.system() == 'linux'
    gnome.post_install(
    	gtk_update_icon_cache: true,
    	update_desktop_database: true,
    )
endif

# freeze
if host_machine.system() == 'windows'
    nsi = configure_file(
        input: 'build-aux' / 'windows' / 'build_installer.nsi.in',
        output: 'build_installer.nsi',
        configuration: conf
    )

    run_target('freeze', command: ['build-aux' / 'freeze.py', get_option('prefix'), meson.project_build_root()])
    run_target('makensis', command: ['makensis', nsi])
endif
