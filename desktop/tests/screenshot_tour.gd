extends SceneTree
# Walks the work window through its pages and states and saves a PNG of each, so the window can be reviewed
# without a person clicking through it.  Run against a backend started with LULU_FAKE_MODEL=1:
#   LULU_CONNECTION=<home>/data/connection.json LULU_SHOTS=<dir> godot --path desktop -s res://tests/screenshot_tour.gd
var pet
var shots := ''
var n := 0

func _initialize(): call_deferred('run')

func shot(name: String):
	await create_timer(0.35).timeout
	await RenderingServer.frame_post_draw
	await RenderingServer.frame_post_draw
	n += 1
	var img = pet.panel.get_texture().get_image()
	img.save_png(shots.path_join('%02d-%s.png' % [n, name]))
	print('SHOT ', name, ' ', img.get_width(), 'x', img.get_height())

func run():
	shots = OS.get_environment('LULU_SHOTS')
	if shots.is_empty(): shots = '/tmp/lulu-shots'
	DirAccess.make_dir_recursive_absolute(shots)
	pet = load('res://main.tscn').instantiate(); root.add_child(pet)
	await create_timer(1.0).timeout
	for i in range(40):
		await pet.poll()
		if pet.connected: break
		await create_timer(0.25).timeout
	pet.show_panel()
	await pet.new_session()
	await pet.refresh()
	await create_timer(0.5).timeout
	await shot('chat-empty')
	# a conversation with the fake model
	pet.prompt.text = '你好呀'
	await pet.submit()
	for i in range(30):
		await create_timer(0.3).timeout
		await pet.poll()
		if not pet.task_active: break
	await pet.load_messages()
	await shot('chat-after-reply')
	# tag pressed: options row
	if pet.tag_buttons.has('translate'):
		pet.tag_buttons['translate'].button_pressed = true
		await shot('tag-translate')
		pet.tag_buttons['extract'].button_pressed = true
		await shot('tag-extract')
		pet.tag_buttons['extract'].button_pressed = false
	for tab in range(1, pet.tabs.get_tab_count()):
		pet.nav_buttons[tab].button_pressed = true
		var title = pet.tabs.get_tab_title(tab)
		if title == '设置': await pet.load_backend()
		await shot('page-' + title)
		if title == '文件' and pet.file_list.item_count > 0:
			# P01 (2026-09-08 真机): a focused list used to paint over its rows; click a row and keep focus on it
			pet.file_list.grab_focus(); pet.file_list.select(0); pet.file_list.item_selected.emit(0)
			await shot('page-文件-选中一行')
		if title == '设置':
			# P05: changing the backend dropdown must survive the periodic poll until 应用 is pressed
			pet.backend_option.select(1); pet.backend_option.item_selected.emit(1)
			await shot('page-设置-改成API未应用')
			await pet.poll(); await pet.poll()
			print('SETTINGS_KEEPS_EDIT ', pet.backend_option.selected == 1)
			await shot('page-设置-轮询后')
			pet.backend_option.select(0); pet.backend_option.item_selected.emit(0)
	pet.go_chat()
	# the 补充一下 card sits inside the work window above the composer
	pet.question_body.text = '还差一点信息\n\n要把 报告.md 转成什么格式？'
	for o in ['PDF', 'Word', 'Markdown']:
		var b = Button.new(); b.text = o; pet.question_options.add_child(b)
	pet.question_card.show()
	await shot('question-card')
	pet.question_card.hide()
	# 界面大小: the same page at 标准 / 大 / 特大
	for i in range(pet.UI_SCALES.size()):
		pet.set_ui_scale(pet.UI_SCALES[i])
		await shot('scale-' + pet.UI_SCALE_NAMES[i])
	pet.set_ui_scale(1.15)
	# the pet itself (buttons centred under the frame)
	await create_timer(0.3).timeout
	await RenderingServer.frame_post_draw
	pet.get_viewport().get_texture().get_image().save_png(shots.path_join('95-pet.png'))
	print('TOUR_DONE ', n)
	quit()
