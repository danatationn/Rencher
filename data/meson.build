### METAINFO ###
if host_machine.system() == 'linux'
	install_data(
	'com.github.danatationn.rencher.metainfo.xml',
		install_dir: get_option('datadir') / 'metainfo'
	)
endif

### DESKTOP FILE ###
desktop = configure_file(
	input: app_id + '.desktop.in',
	output: app_id + '.desktop',
	configuration: conf,
	install: true,
	install_dir: join_paths(get_option('datadir'), 'applications'),
	install_mode: 'rwxr-xr-x'
)

### UI FILES ###
blueprint = custom_target('blueprint',
	input: files(
		'ui/import.blp',
		'ui/options.blp',
		'ui/settings.blp',
		'ui/shortcuts.blp',
		'ui/window.blp',
		'ui/game_detail_view.blp',
	),
	output: '.',
	build_always_stale: true,
	build_by_default: true,
	command: [find_program('blueprint-compiler'), 'batch-compile', '@OUTPUT@', '@CURRENT_SOURCE_DIR@', '@INPUT@'],
)

### ICONS ###
icons = [
	['16x16', 'assets/rencher-icon16.png'],
	['32x32', 'assets/rencher-icon32.png'],
	['48x48', 'assets/rencher-icon48.png'],
	['64x64', 'assets/rencher-icon64.png'],
	['128x128', 'assets/rencher-icon128.png'],
	['256x256', 'assets/rencher-icon256.png'],
]
icon_name = '@0@.png'.format(conf.get('app_id'))

foreach icon : icons
	install_data(
		icon[1],
		install_dir: join_paths(
			get_option('datadir'),
			'icons/hicolor',
			icon[0],
			'apps'
		),
		rename: icon_name
	)
endforeach

### GRESOURCE ###
gnome.compile_resources(app_id,
	configure_file(
		input: app_id + '.gresource.xml.in',
		output: app_id + '.gresource.xml',
		configuration: conf
	),
	gresource_bundle: true,
	dependencies: blueprint,
	install: true,
	install_dir: pkgdata_dir
)
