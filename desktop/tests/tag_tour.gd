extends SceneTree
# Drives the work window like a person: press a tag, pick its options, choose files, type, send; then reads the task
# back from the backend and checks that the skill, files and options arrived and the reply showed up in the window.
# Writes <LULU_SHOTS>/tag-tour.json and a screenshot per case.  Backend: LULU_FAKE_MODEL=1 (plumbing check), or a
# real model for capability checks.
var pet
var shots := ''
var results := []

func _initialize(): call_deferred('run')

func shot(name: String):
	await create_timer(0.3).timeout
	await RenderingServer.frame_post_draw
	await RenderingServer.frame_post_draw
	pet.panel.get_texture().get_image().save_png(shots.path_join('tag-%s.png' % name))

func wait_task(max_seconds: float) -> void:
	var waited := 0.0
	while waited < max_seconds:
		await create_timer(0.4).timeout
		waited += 0.4
		await pet.poll()
		if not pet.task_active and not pet.request_pending: return

func set_option(key: String, value: String) -> bool:
	if not pet.option_widgets.has(key): return false
	var ob = pet.option_widgets[key]
	for i in range(ob.item_count):
		if ob.get_item_text(i) == value:
			ob.select(i); return true
	return false

func run_case(name: String, tag: String, text: String, options: Dictionary, files: Array, expect: Dictionary):
	pet.clear_picked_files()
	if not tag.is_empty(): pet.tag_buttons[tag].button_pressed = true
	else:
		var current = pet.selected_tag()
		if not current.is_empty(): pet.tag_buttons[current].button_pressed = false
	await create_timer(0.1).timeout
	var option_ok := true
	for key in options:
		if key == 'columns':
			if pet.columns_input == null: option_ok = false
			else: pet.columns_input.text = str(options[key])
		elif not set_option(key, str(options[key])): option_ok = false
	pet.picked_files = files.duplicate(); pet.update_file_chip()
	pet.prompt.text = text
	var before: int = pet.chat_box.get_child_count()
	await pet.submit()
	await wait_task(40)
	await pet.load_messages()
	await shot(name)
	var task := {}
	if not pet.task_id.is_empty():
		task = await pet.bridge.request_api(HTTPClient.METHOD_GET, 'tasks/' + pet.task_id)
	var t = task.get('task', {})
	var intent = JSON.parse_string(str(t.get('intent', '{}'))) if t.has('intent') else {}
	var forced = intent.get('forced', {}) if intent is Dictionary else {}
	var kinds: Array = []
	for e in task.get('events', []): kinds.append(str(e.kind))
	var record := {'case': name, 'tag': tag, 'text': text, 'options_set_ok': option_ok, 'status': str(t.get('status', '')), 'answer': str(t.get('answer', '')).left(300),
		'forced_skill': str(forced.get('skill', '')), 'forced_files': forced.get('files', []), 'forced_options': forced.get('options', {}),
		'skill_started': kinds.has('skill_started'), 'classifier_called': kinds.has('thinking'), 'bubbles_added': pet.chat_box.get_child_count() - before,
		'pending_question': not pet.questions.is_empty()}
	var problems: Array = []
	if expect.has('skill') and record.forced_skill != expect.skill: problems.append('skill %s != %s' % [record.forced_skill, expect.skill])
	if expect.has('status') and record.status != expect.status: problems.append('status %s != %s' % [record.status, expect.status])
	if expect.has('contains') and not record.answer.contains(str(expect.contains)): problems.append('answer lacks ' + str(expect.contains))
	if expect.has('files') and str(record.forced_files) != str(expect.files): problems.append('files %s != %s' % [str(record.forced_files), str(expect.files)])
	for key in expect.get('options', {}):
		if str(record.forced_options.get(key, '')) != str(expect.options[key]): problems.append('option %s=%s != %s' % [key, str(record.forced_options.get(key, '')), str(expect.options[key])])
	if not option_ok: problems.append('option widget missing')
	if record.bubbles_added < 1 and not record.pending_question: problems.append('nothing appeared in the chat')
	record['problems'] = problems
	results.append(record)
	print('CASE ', name, ' ', 'PASS' if problems.is_empty() else 'FAIL ' + str(problems), ' status=', record.status, ' answer=', record.answer.left(60))
	if not tag.is_empty(): pet.tag_buttons[tag].button_pressed = false
	if record.pending_question:
		# answer with the first option or a short reply so the next case starts clean
		await pet.bridge.request_api(HTTPClient.METHOD_POST, 'questions/' + str(pet.questions[0].id) + '/answer', {'action': 'cancel'})
		await create_timer(0.3).timeout
		await pet.poll()

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
	await run_case('translate-text', 'translate', '会议改到9月20日下午三点，预算仍是18650元。', {'lang': '英文'}, [], {'skill': 'translate', 'status': 'completed', 'options': {'lang': '英文'}})
	await run_case('translate-file', 'translate', '', {'lang': '英文'}, ['说明.md'], {'skill': 'translate', 'status': 'completed', 'files': ['说明.md'], 'contains': '译文-说明'})
	await run_case('summarize-file', 'summarize', '', {'length': '几条要点'}, ['纪要.md'], {'skill': 'summarize', 'status': 'completed', 'files': ['纪要.md']})
	await run_case('summarize-text', 'summarize', '会议决定：项目代号青松731，负责人陆遥，预算 18650，截止 2026-11-23，参与 17 人。下一步周文整理需求，何晴联系供应商。', {'length': '一句话'}, [], {'skill': 'summarize', 'status': 'completed'})
	await run_case('rewrite', 'rewrite', '那个，我们这边呢，大概就是想说预算 18650 这个事情可能要再讨论讨论。', {'tone': '更正式'}, [], {'skill': 'rewrite', 'status': 'completed', 'options': {'tone': '更正式'}})
	await run_case('ask-file', 'ask_file', '付款期限是多久？', {}, ['合同.md'], {'skill': 'ask_file', 'status': 'completed', 'files': ['合同.md']})
	await run_case('ask-file-nofile', 'ask_file', '付款期限是多久？', {}, [], {'skill': 'ask_file'})
	await run_case('extract', 'extract', '', {'columns': '姓名、电话、金额', 'out_format': 'Excel'}, ['名单.md'], {'skill': 'extract', 'status': 'completed', 'files': ['名单.md'], 'options': {'out_format': 'Excel'}})
	await run_case('generate-points', 'generate', '本周完成登录页和支付联调，修了 7 个缺陷；下周压测和上线准备；风险：供应商测试环境未到。', {'doc_kind': '周报', 'out_format': 'Word'}, [], {'skill': 'generate', 'status': 'completed', 'options': {'doc_kind': '周报', 'out_format': 'Word'}})
	await run_case('generate-empty', 'generate', '写一份周报', {'doc_kind': '周报'}, [], {'skill': 'generate', 'status': 'awaiting_input'})
	await run_case('convert', 'convert', '', {'out_format': 'PDF'}, ['报告.md'], {'skill': 'convert', 'status': 'completed', 'files': ['报告.md'], 'contains': '报告.pdf'})
	await run_case('record-note', 'record', '周四下午和供应商开会', {'memory_target': '今天的笔记'}, [], {'skill': 'record', 'status': 'completed', 'contains': '记下了'})
	await run_case('record-memory', 'record', '我的邮件署名用小沈', {'memory_target': '长期记忆'}, [], {'skill': 'record', 'status': 'completed', 'contains': '记住了'})
	await run_case('remind', 'remind', '明天早上八点提醒我开周会', {}, [], {'skill': 'remind', 'status': 'completed', 'contains': '提醒你'})
	await run_case('query-local', 'query', '供应商', {'scope': '本地文件'}, [], {'skill': 'query', 'status': 'completed', 'contains': '找到'})
	await run_case('query-web-offline', 'query', '比特币每四年减半是真的吗', {'scope': '网上'}, [], {'skill': 'query'})
	await run_case('chat', 'chat', '你是谁呀', {}, [], {'skill': 'chat', 'status': 'completed'})
	await run_case('free-text-no-tag', '', '把 报告.md 转成pdf', {}, [], {'status': 'completed'})
	var f = FileAccess.open(shots.path_join('tag-tour.json'), FileAccess.WRITE)
	f.store_string(JSON.stringify(results, '  ')); f.close()
	var failed: int = 0
	for r in results: if not r.problems.is_empty(): failed += 1
	print('TAG_TOUR_DONE ', results.size() - failed, '/', results.size())
	quit()
