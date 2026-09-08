extends Control
const AnimationState = preload('res://src/animation_state.gd')
const BridgeClient = preload('res://src/bridge_client.gd')
var animation
var bridge
var manifest: Dictionary
const FrameStore=preload('res://src/frame_store.gd')
const AnimationLab=preload('res://src/animation_lab.gd')
var frames
var frames_missing := false
var transition_material: ShaderMaterial
var lab
var pet_scale=1.0
var display_frame=241
var blend_from=241
var last_display_phase='idle'
var loading=false
var last_draw_frame: int = -1
var last_draw_from: int = -1
var last_draw_blend: float = -1.0
var panel: Window
var prompt: TextEdit
var status: Label
var pet_chrome: Control
var composer: PanelContainer
var questions: Array=[]
var question_card: PanelContainer
var ui_scale: float=1.15
var ui_scale_option: OptionButton
var question_body: Label
var question_reply: TextEdit
var question_send: Button
var question_id=''
var question_seen=''
var record_window: Window
var record_body: TextEdit
var record_task=''
var record_poll=0.0
var record_refreshing=false
var pet_status: Label
var weather_label: Label
var run_button: Button
var cancel_button: Button
var read_button: Button
var quit_button: Button
var city_input: LineEdit
var city_options: OptionButton
var cities: Array = []
var reminder_rows: VBoxContainer
var reminder_signature := ''
var task_id := ''
var task_active := false
var task_status := ''
var polling := false
var poll_time := 1.0
var diagnostic_time := 0.0
var last_transition := -1
var blend_time := 1.0
var drag := false
var drag_moved := false
var drag_pointer := Vector2i.ZERO
var last_care_id := -1
var drag_start := Vector2i.ZERO
var alert: Window
var alert_label: Label
var due_items: Array = []
var shown_due := ''
var shutting_down := false
var tabs: TabContainer
var memory_list: ItemList
var file_list: ItemList
var task_list: ItemList
var reminder_list: ItemList
var memory_key: LineEdit
var memory_value: LineEdit
var sessions: OptionButton
var memories: Array = []
var files: Array = []
var tasks: Array = []
var reminders: Array = []
var session_id := ''
var resume_id := ''
var workspace := ''
var refreshing := false
var refresh_time := 10.0
var last_frame := -1
var previous_status := ''
var connected := false
var request_pending := false
var started_ms := 0
var file_dialog: FileDialog
var notice_popup: AcceptDialog
var candidate_list: ItemList
var candidate_label: Label
var candidates: Array = []
var reminder_phrase: LineEdit
var question_options: HBoxContainer
var backend_info: Dictionary = {}
var backend_option: OptionButton
var tier_option: OptionButton
var preset_option: OptionButton
var api_base: LineEdit
var api_model: LineEdit
var api_key: LineEdit
var claude_command: LineEdit
var claude_model: LineEdit
var cli_command: LineEdit
var search_option: OptionButton
var search_key: LineEdit
var think_switch: CheckButton
var backend_status: Label
var backend_body: TextEdit
var backend_tab: VBoxContainer
var local_box: VBoxContainer
var api_box: VBoxContainer
var claude_box: VBoxContainer
var cli_box: VBoxContainer
var backend_busy := false
var backend_loaded := false
var backend_line := ''
var nav_group: ButtonGroup
var nav_buttons: Array = []
var model_pill: Label
var chat_scroll: ScrollContainer
var chat_box: VBoxContainer
var welcome: Label
var pending_button: Button
var tasks_window: Window
var tag_row: HFlowContainer
var tag_group: ButtonGroup
var tag_buttons: Dictionary = {}
var option_row: HBoxContainer
var option_widgets: Dictionary = {}
var columns_input: LineEdit
var picked_files: Array = []
var file_chip: Button
var file_picker: Window
var picker_list: ItemList
var composer_hint: Label
var last_artifact := ''
const TAGS := [
	{'key':'translate','label':'翻译','hint':'贴上要翻译的文字，或选一个文件','options':['lang']},
	{'key':'summarize','label':'总结','hint':'贴上内容，或选一个文件，我帮你整理要点','options':['length','out_format_doc']},
	{'key':'rewrite','label':'改写润色','hint':'贴上原文，说说想怎么改','options':['tone']},
	{'key':'ask_file','label':'问文件','hint':'选好文件，再说说你想知道什么','options':[]},
	{'key':'extract','label':'提取成表','hint':'选文件或贴上内容，告诉我表里要放哪些信息','options':['columns','out_format_table']},
	{'key':'generate','label':'按要点写','hint':'把要点发给我，我帮你写成一篇','options':['doc_kind','out_format_doc']},
	{'key':'convert','label':'转格式','hint':'选好文件，再选要转成的格式','options':['out_format_convert']},
	{'key':'record','label':'记一下','hint':'有什么要记的，直接告诉我','options':['memory_target']},
	{'key':'remind','label':'提醒','hint':'比如：明天早上8点提醒我开会','options':[]},
	{'key':'query','label':'查一下','hint':'告诉我想查什么，再选去哪里找','options':['scope']},
	{'key':'chat','label':'聊聊天','hint':'今天怎么样？随便聊聊吧','options':[]},
]
const OPTION_SETS := {
	'lang':{'label':'翻成','key':'lang','values':['自动判断','英文','中文','日文','韩文','法语','德语','西班牙语','俄语']},
	'length':{'label':'长度','key':'length','values':['几条要点','一句话','一段话']},
	'tone':{'label':'怎么改','key':'tone','values':['更自然','更正式','更客气','更简短','更详细','删掉多余的话','整理成要点','连成段落','只改错别字和标点']},
	'doc_kind':{'label':'写什么','key':'doc_kind','values':['邮件','通知','周报','会议纪要','说明','计划','清单']},
	'out_format_doc':{'label':'结果','key':'out_format','values':['直接显示','Word','PDF','Markdown']},
	'out_format_table':{'label':'结果','key':'out_format','values':['直接显示','Excel','CSV']},
	'out_format_convert':{'label':'转成','key':'out_format','values':['PDF','Word','Markdown','纯文本','Excel']},
	'scope':{'label':'去哪里找','key':'scope','values':['都查','本地文件','网上']},
	'memory_target':{'label':'记到','key':'memory_target','values':['今天的笔记','长期记忆']},
}
const UI_SCALES := [1.0,1.15,1.3]
const UI_SCALE_NAMES := ['标准','大','特大']
const DEFAULT_HINT := '想做什么，直接告诉我。也可以先选上面的标签。'
const BACKEND_KEYS := ['ollama','api','claude_cli','cli']
const BACKEND_NAMES := ['本地模型（Ollama）','API 接口（使用自己的密钥）','Claude 命令行（claude -p）','其他命令行（如 codex exec）']
const TIER_KEYS := ['auto','4b','8b','custom']
const TIER_NAMES := ['自动选择（按内存）','4B · 双模型（8GB 内存档）','8B · 混合模型（16GB 内存起）','自定义（编辑 config.json）']
const PRESET_KEYS := ['dashscope','dashscope_intl','deepseek','openrouter','lmstudio','custom']
const PRESET_NAMES := ['通义千问（阿里云百炼）','通义千问（国际站）','DeepSeek','OpenRouter','LM Studio（本机）','自定义地址']
const SEARCH_KEYS := ['auto','bocha','tavily','brave','engines','none']
const SEARCH_NAMES := ['自动选择（优先使用已保存的密钥）','博查（国内）','Tavily','Brave Search','不用密钥（可能不稳定）','关闭联网搜索']
const SEARCH_SECRETS := {'bocha':'bocha_key','tavily':'tavily_key','brave':'brave_key'}
func _ready():
	get_viewport().transparent_bg = true
	get_window().content_scale_size=Vector2i(528,420)
	get_window().content_scale_mode=Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	get_window().content_scale_aspect=Window.CONTENT_SCALE_ASPECT_KEEP
	manifest = JSON.parse_string(FileAccess.get_file_as_string('res://assets/clips.json'))
	animation = AnimationState.new(manifest)
	frames_missing = not load_frame_pack()
	frames=FrameStore.new(manifest)
	display_frame=int(manifest.idle[0]);blend_from=display_frame
	get_window().size=Vector2i(528,420)
	transition_material=ShaderMaterial.new();transition_material.shader=preload('res://src/transition.gdshader');material=transition_material
	bridge = BridgeClient.new(); add_child(bridge); bridge.set_process(false)
	get_tree().auto_accept_quit = false
	var area = DisplayServer.screen_get_usable_rect()
	get_window().position = area.position + area.size - Vector2i(550,465)
	pet_chrome=Control.new();pet_chrome.mouse_filter=Control.MOUSE_FILTER_IGNORE;add_child(pet_chrome)
	var frame=TextureRect.new();frame.texture=load('res://assets/ui/lulu-speech-frame.png');frame.expand_mode=TextureRect.EXPAND_IGNORE_SIZE;frame.stretch_mode=TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	frame.position=Vector2(84,294);frame.size=Vector2(360,120);frame.mouse_filter=Control.MOUSE_FILTER_IGNORE;pet_chrome.add_child(frame)
	pet_chrome.theme=ui_theme()
	pet_status=Label.new();pet_status.position=Vector2(116,324);pet_status.size=Vector2(296,24);pet_status.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
	pet_status.add_theme_font_size_override('font_size',15);pet_status.add_theme_color_override('font_color',Color('#5a4b3b'));pet_chrome.add_child(pet_status)
	var row=HBoxContainer.new();row.position=Vector2(84,356);row.size=Vector2(360,30);row.alignment=BoxContainer.ALIGNMENT_CENTER;row.add_theme_constant_override('separation',6);pet_chrome.add_child(row)
	button(row,'聊聊天',show_panel)
	read_button=button(row,'陪伴',toggle_reading)
	make_panel();make_alert();make_agent_dialogs();panel.show();alert.hide()
	lab=AnimationLab.new(self);add_child(lab)
	if '--animation-test' in OS.get_cmdline_user_args():button(row,'动作',func():lab.open())
	quit_button=button(row,'退出',begin_quit)
	if '--animation-test' in OS.get_cmdline_user_args():lab.open()
	# Test/review automation is opt-in; normal startup leaves the assistant panel closed.
	if '--review' in OS.get_cmdline_user_args(): panel.show()
	Engine.max_fps=30
	if not OS.get_environment('LULU_CAPTURE').is_empty():call_deferred('capture_preview')
func load_frame_pack() -> bool:
	# Exported builds keep the animation frames (~360MB) outside the main program as frames.pck, downloaded by the
	# install script; the development tree has them under res://assets already. Returns false when neither is there.
	if FileAccess.file_exists('res://assets/optimized.json'):return true
	var candidates: Array[String]=[]
	var given=OS.get_environment('LULU_FRAMES')
	if not given.is_empty():candidates.append(given)
	var exe_dir=OS.get_executable_path().get_base_dir()
	for rel in ['frames.pck','../frames.pck','../Resources/frames.pck','../../frames.pck','../../../frames.pck']:
		candidates.append(exe_dir.path_join(rel).simplify_path())
	for path in candidates:
		if FileAccess.file_exists(path) and ProjectSettings.load_resource_pack(path,false):
			print('frames: ',path);return FileAccess.file_exists('res://assets/optimized.json')
	push_warning('frames.pck not found; looked in '+str(candidates))
	return false
func load_ui_scale() -> float:
	# 界面大小 lives in user://ui.json; default is one notch up from 1:1 because 15px text reads small on a laptop screen.
	if FileAccess.file_exists('user://ui.json'):
		var data=JSON.parse_string(FileAccess.get_file_as_string('user://ui.json'))
		if data is Dictionary and data.has('scale') and float(data.scale) in UI_SCALES: return float(data.scale)
	return 1.15
func set_ui_scale(scale: float):
	# the window grows with the content so the chat page keeps the same room at every size
	ui_scale=scale; panel.content_scale_factor=scale
	panel.min_size=Vector2i(Vector2(860,620)*scale)
	panel.size=Vector2i(Vector2(1040,740)*scale)
	var area=DisplayServer.screen_get_usable_rect()
	panel.size=Vector2i(mini(panel.size.x,area.size.x-40),mini(panel.size.y,area.size.y-60))
	panel.position=Vector2i(maxi(area.position.x,mini(panel.position.x,area.end.x-panel.size.x)),maxi(area.position.y,mini(panel.position.y,area.end.y-panel.size.y)))
	var f=FileAccess.open('user://ui.json',FileAccess.WRITE)
	if f: f.store_string(JSON.stringify({'scale':scale})); f.close()
func window_background(window: Window):
	var bg=ColorRect.new();bg.color=Color('#faf7f1');bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);window.add_child(bg)
func ui_theme() -> Theme:
	var theme=Theme.new();theme.default_font_size=15
	for kind in ['Label','Button','TextEdit','LineEdit','ItemList','TabContainer','OptionButton','SpinBox']:
		for key in ['font_color','font_readonly_color','font_selected_color','font_pressed_color','font_hover_pressed_color','font_hover_color','font_focus_color']:theme.set_color(key,kind,Color('#4a3f33'))
		theme.set_color('font_unselected_color',kind,Color('#8a7b69'));theme.set_color('font_placeholder_color',kind,Color('#a0937f'));theme.set_color('font_disabled_color',kind,Color('#b3a892'))
		theme.set_color('caret_color',kind,Color('#b8964e'));theme.set_color('selection_color',kind,Color('#e7d7b6'))
		if kind=='Label':continue
		for state in ['normal','read_only','hover','pressed','focus','disabled','panel','tab_selected','tab_unselected']:
			var box=StyleBoxFlat.new();box.bg_color=Color('#fdfbf6');box.border_color=Color('#dfd3bd');box.set_border_width_all(1);box.set_corner_radius_all(12)
			if kind in ['Button','OptionButton'] or state=='tab_selected':box.bg_color=Color('#efe4cf')
			if state in ['hover','focus']:box.bg_color=Color('#f4ead6');box.border_color=Color('#c9ab6e')
			if kind=='ItemList' and state=='focus':box.draw_center=false  # drawn on top of the rows: border only, or the list goes blank on click
			if state=='pressed':box.bg_color=Color('#d9b978');box.border_color=Color('#b8964e')
			box.content_margin_left=10;box.content_margin_right=10;box.content_margin_top=7;box.content_margin_bottom=7;theme.set_stylebox(state,kind,box)
	# List rows: a clear hover band and a solid selection so the pointer target is obvious.
	for state in ['hovered','selected','selected_focus','cursor','cursor_unfocused']:
		var row=StyleBoxFlat.new();row.set_corner_radius_all(8);row.content_margin_left=8;row.content_margin_right=8;row.content_margin_top=5;row.content_margin_bottom=5
		row.bg_color=Color('#f3eadb') if state=='hovered' else Color('#e3cfa6');row.border_color=Color('#c9ab6e');row.set_border_width_all(1 if state.begins_with('cursor') else 0)
		if state.begins_with('cursor'):row.draw_center=false  # the cursor box is painted over the row text: outline only
		theme.set_stylebox(state,'ItemList',row)
	theme.set_color('font_hovered_color','ItemList',Color('#3d342a'));theme.set_color('font_selected_color','ItemList',Color('#3d342a'))
	theme.set_constant('v_separation','ItemList',6);theme.set_constant('h_separation','ItemList',8);theme.set_constant('line_separation','ItemList',4)
	return theme
func button(parent: Node, title: String, action: Callable) -> Button:
	var b = Button.new();b.text = title;b.pressed.connect(action);parent.add_child(b);return b
func label(parent: Node, text: String) -> Label:
	var l = Label.new();l.text=text;l.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;parent.add_child(l);return l
func plain_label(parent: Node, text: String) -> Label:
	# No wrapping: inside a flow/box row a wrapping label collapses to one character per line.
	var l = Label.new();l.text=text;l.add_theme_font_size_override('font_size',13);l.size_flags_vertical=Control.SIZE_SHRINK_CENTER;parent.add_child(l);return l
func make_panel():
	panel=Window.new(); panel.title='Lulu · 你的工作伙伴'; panel.size=Vector2i(1040,740); panel.min_size=Vector2i(860,620)
	panel.transparent=false; panel.borderless=false; panel.always_on_top=false; panel.close_requested.connect(func(): panel.hide()); add_child(panel)
	panel.content_scale_mode=Window.CONTENT_SCALE_MODE_CANVAS_ITEMS; panel.content_scale_aspect=Window.CONTENT_SCALE_ASPECT_IGNORE; ui_scale=load_ui_scale(); panel.content_scale_factor=ui_scale; panel.size=Vector2i(Vector2(1040,740)*ui_scale); panel.min_size=Vector2i(Vector2(860,620)*ui_scale)
	panel.position=DisplayServer.screen_get_usable_rect().position+Vector2i(60,70)
	var background=ColorRect.new(); background.color=Color('#faf7f1'); background.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT); panel.add_child(background)
	var root=HBoxContainer.new(); root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT); root.add_theme_constant_override('separation',0); panel.add_child(root)
	root.theme=ui_theme()
	# ---- left rail: name, pages, model pill
	var rail_panel=PanelContainer.new(); rail_panel.custom_minimum_size=Vector2(170,0); root.add_child(rail_panel)
	var rail_box=StyleBoxFlat.new(); rail_box.bg_color=Color('#f1ebe0'); rail_box.content_margin_left=16; rail_box.content_margin_right=12; rail_box.content_margin_top=22; rail_box.content_margin_bottom=16; rail_panel.add_theme_stylebox_override('panel',rail_box)
	var rail=VBoxContainer.new(); rail.add_theme_constant_override('separation',6); rail_panel.add_child(rail)
	var heading=Label.new(); heading.text='lulu'; heading.add_theme_font_size_override('font_size',28); heading.add_theme_color_override('font_color',Color('#5a4b3b')); rail.add_child(heading)
	var tagline=Label.new(); tagline.text='今天也陪着你'; tagline.add_theme_font_size_override('font_size',14); tagline.add_theme_color_override('font_color',Color('#8a7b69')); rail.add_child(tagline)
	rail.add_child(spacer(18))
	nav_group=ButtonGroup.new()
	for item in [['对话',0],['文件',1],['记忆',2],['提醒',3],['设置',4]]:
		var b=Button.new(); b.text=str(item[0]); b.toggle_mode=true; b.button_group=nav_group; b.alignment=HORIZONTAL_ALIGNMENT_LEFT; b.add_theme_font_size_override('font_size',16)
		b.flat=false; b.add_theme_stylebox_override('normal',flat_box(Color(0,0,0,0))); b.add_theme_stylebox_override('hover',flat_box(Color('#ebe1cd')))
		b.add_theme_stylebox_override('pressed',flat_box(Color('#e3cfa6'))); b.add_theme_stylebox_override('focus',flat_box(Color(0,0,0,0)))
		var idx=int(item[1]); b.toggled.connect(func(on): if on: tabs.current_tab=idx; if on and idx==4: load_backend())
		rail.add_child(b); nav_buttons.append(b)
	var filler=Control.new(); filler.size_flags_vertical=Control.SIZE_EXPAND_FILL; rail.add_child(filler)
	model_pill=Label.new(); model_pill.text='正在连接…'; model_pill.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART; model_pill.add_theme_font_size_override('font_size',13); model_pill.add_theme_color_override('font_color',Color('#6f6252')); rail.add_child(model_pill)
	var footer=Label.new(); footer.text='记忆留在这台电脑'; footer.add_theme_font_size_override('font_size',12); footer.add_theme_color_override('font_color',Color('#a0937f')); rail.add_child(footer)
	# ---- main column
	var main=MarginContainer.new(); main.size_flags_horizontal=Control.SIZE_EXPAND_FILL; root.add_child(main)
	for key in ['margin_left','margin_right','margin_top','margin_bottom']: main.add_theme_constant_override(key,18)
	var layout=column(main,'Layout'); layout.add_theme_constant_override('separation',8)
	status=Label.new(); status.text='正在连接本机服务…'; status.text_overrun_behavior=TextServer.OVERRUN_TRIM_ELLIPSIS; status.custom_minimum_size=Vector2(0,20); status.add_theme_font_size_override('font_size',14); status.add_theme_color_override('font_color',Color('#7d6e5d')); layout.add_child(status)
	tabs=TabContainer.new(); tabs.tabs_visible=false; tabs.size_flags_vertical=Control.SIZE_EXPAND_FILL; layout.add_child(tabs)
	tabs.add_theme_stylebox_override('panel',flat_box(Color(0,0,0,0)))
	nav_buttons[0].set_pressed_no_signal(true)
	# -- 对话
	var chat=column(tabs,'对话'); chat.add_theme_constant_override('separation',8)
	var top=HBoxContainer.new(); top.add_theme_constant_override('separation',8); chat.add_child(top)
	sessions=OptionButton.new(); sessions.size_flags_horizontal=Control.SIZE_EXPAND_FILL; sessions.add_theme_font_size_override('font_size',14); top.add_child(sessions)
	sessions.item_selected.connect(func(i): session_id=str(sessions.get_item_metadata(i)); task_id=''; load_messages())
	button(top,'新对话',new_session)
	pending_button=button(top,'没做完的',func(): open_tasks_window()); pending_button.visible=false
	button(top,'执行记录',func():show_record())
	chat_scroll=ScrollContainer.new(); chat_scroll.size_flags_vertical=Control.SIZE_EXPAND_FILL; chat_scroll.horizontal_scroll_mode=ScrollContainer.SCROLL_MODE_DISABLED; chat.add_child(chat_scroll)
	chat_box=VBoxContainer.new(); chat_box.size_flags_horizontal=Control.SIZE_EXPAND_FILL; chat_box.add_theme_constant_override('separation',10); chat_scroll.add_child(chat_box)
	welcome=Label.new(); welcome.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART; welcome.add_theme_font_size_override('font_size',16); welcome.add_theme_color_override('font_color',Color('#7d6e5d'))
	welcome.text='嗨，我是 Lulu。可以帮你处理文件、整理文字、记事和设提醒。\n\n试着说：\n· 总结一下纪要.docx\n· 把报告.md转成PDF\n· 按这些要点写封邮件：……\n· 明天早上8点提醒我开会\n\n也可以先点输入框上面的标签，再打字。'
	chat_box.add_child(welcome)
	composer=PanelContainer.new();chat.add_child(composer)
	var composer_box=StyleBoxFlat.new();composer_box.bg_color=Color('#f6f1e6');composer_box.border_color=Color('#d9c9a8');composer_box.set_border_width_all(1);composer_box.set_corner_radius_all(16)
	composer_box.content_margin_left=14;composer_box.content_margin_right=14;composer_box.content_margin_top=10;composer_box.content_margin_bottom=10;composer.add_theme_stylebox_override('panel',composer_box)
	var composer_col=column(composer,'输入');composer_col.add_theme_constant_override('separation',8)
	composer_hint=label(composer_col,DEFAULT_HINT);composer_hint.add_theme_font_size_override('font_size',14);composer_hint.add_theme_color_override('font_color',Color('#7d6e5d'))
	make_tag_row(composer_col)
	prompt=TextEdit.new(); prompt.custom_minimum_size=Vector2(0,88); prompt.wrap_mode=TextEdit.LINE_WRAPPING_BOUNDARY; prompt.placeholder_text='输入你想做的事，或和 Lulu 聊聊…'; prompt.add_theme_font_size_override('font_size',15); composer_col.add_child(prompt)
	prompt.gui_input.connect(func(event):
		if event is InputEventKey and event.pressed and event.keycode==KEY_ENTER and (event.ctrl_pressed or event.meta_pressed): submit(); get_viewport().set_input_as_handled())
	var controls=HBoxContainer.new(); controls.add_theme_constant_override('separation',8); composer_col.add_child(controls)
	run_button=button(controls,'发给 Lulu →',submit); run_button.add_theme_font_size_override('font_size',15); cancel_button=button(controls,'停止',cancel); cancel_button.disabled=true
	var hint=label(controls,'Ctrl / ⌘ + Enter 发送');hint.add_theme_font_size_override('font_size',12);hint.add_theme_color_override('font_color',Color('#a0937f'));hint.size_flags_horizontal=Control.SIZE_EXPAND_FILL;hint.horizontal_alignment=HORIZONTAL_ALIGNMENT_RIGHT
	# -- 文件
	var file_tab=column(tabs,'文件'); file_tab.add_theme_constant_override('separation',10)
	page_title(file_tab,'文件','把要用的文件添加到这里。单击选中（可多选），双击打开；选好后点“用它来对话”。')
	file_list=list_box(file_tab); file_list.select_mode=ItemList.SELECT_MULTI; file_list.item_activated.connect(func(i): open_file())
	var fr=HBoxContainer.new(); fr.add_theme_constant_override('separation',8); file_tab.add_child(fr)
	button(fr,'添加文件…',func(): file_dialog.popup_centered_ratio(.75)); button(fr,'打开',open_file); button(fr,'用它来对话',use_file)
	button(fr,'打开文件夹',func(): if not workspace.is_empty(): OS.shell_open(workspace))
	# -- 记忆
	var memory_tab=column(tabs,'记忆'); memory_tab.add_theme_constant_override('separation',10)
	page_title(memory_tab,'记忆','已记住的内容，聊天时会参考。选一条可以改或删。')
	memory_list=list_box(memory_tab)
	var mk=HBoxContainer.new(); mk.add_theme_constant_override('separation',8); memory_tab.add_child(mk)
	memory_key=LineEdit.new(); memory_key.placeholder_text='名称，例如：回答风格'; memory_key.custom_minimum_size=Vector2(220,0); mk.add_child(memory_key)
	memory_value=LineEdit.new(); memory_value.placeholder_text='要长期记住的偏好或事实'; memory_value.size_flags_horizontal=Control.SIZE_EXPAND_FILL; mk.add_child(memory_value)
	memory_list.item_selected.connect(func(i): memory_key.text=str(memories[i].key); memory_value.text=str(memories[i].value))
	var mr=HBoxContainer.new(); mr.add_theme_constant_override('separation',8); memory_tab.add_child(mr); button(mr,'保存 / 修改',save_memory); button(mr,'删除所选',delete_memory)
	candidate_label=label(memory_tab,'要记住这些吗？点“记住”后才会保存。');candidate_label.add_theme_font_size_override('font_size',15)
	candidate_list=list_box(memory_tab); candidate_list.custom_minimum_size=Vector2(0,90); candidate_list.size_flags_vertical=Control.SIZE_FILL
	var cr=HBoxContainer.new(); cr.add_theme_constant_override('separation',8); memory_tab.add_child(cr); button(cr,'记住',func(): resolve_candidate(true)); button(cr,'忽略',func(): resolve_candidate(false))
	# -- 提醒
	var reminder_tab=column(tabs,'提醒'); reminder_tab.add_theme_constant_override('separation',10)
	page_title(reminder_tab,'提醒','告诉我时间和事情就行，比如“明天早上8点提醒我开会”或“每天9点提醒我喝水”。')
	var nr=HBoxContainer.new(); nr.add_theme_constant_override('separation',8); reminder_tab.add_child(nr)
	reminder_phrase=LineEdit.new(); reminder_phrase.placeholder_text='明天下午三点提醒我交周报'; reminder_phrase.size_flags_horizontal=Control.SIZE_EXPAND_FILL; nr.add_child(reminder_phrase)
	reminder_phrase.text_submitted.connect(func(_t): parse_reminder()); button(nr,'设提醒',parse_reminder)
	reminder_list=list_box(reminder_tab)
	var rr=HBoxContainer.new(); reminder_tab.add_child(rr)
	button(rr,'标为完成 / 取消所选',ack_reminder)
	# -- 设置（模型 + 陪伴）
	var settings_scroll=ScrollContainer.new(); settings_scroll.name='设置'; settings_scroll.horizontal_scroll_mode=ScrollContainer.SCROLL_MODE_DISABLED; tabs.add_child(settings_scroll)
	var settings=VBoxContainer.new(); settings.size_flags_horizontal=Control.SIZE_EXPAND_FILL; settings.add_theme_constant_override('separation',12); settings_scroll.add_child(settings)
	page_title(settings,'设置','界面、模型、联网搜索和陪伴。')
	var look=HBoxContainer.new(); look.add_theme_constant_override('separation',8); settings.add_child(look)
	var look_label=Label.new(); look_label.text='界面大小'; look.add_child(look_label)
	ui_scale_option=OptionButton.new(); look.add_child(ui_scale_option)
	for name in UI_SCALE_NAMES: ui_scale_option.add_item(name)
	ui_scale_option.select(UI_SCALES.find(ui_scale) if ui_scale in UI_SCALES else 1)
	ui_scale_option.item_selected.connect(func(i): set_ui_scale(UI_SCALES[i]))
	var look_hint=label(look,'字太小就调大一档，窗口里的字和按钮一起放大。'); look_hint.add_theme_font_size_override('font_size',14); look_hint.add_theme_color_override('font_color',Color('#7d6e5d'))
	settings.add_child(spacer(6))
	make_backend_tab(settings)
	settings.add_child(spacer(10))
	var care=Label.new(); care.text='陪伴'; care.add_theme_font_size_override('font_size',18); settings.add_child(care)
	weather_label=label(settings,'Lulu 会按网络位置自动找你所在的城市看天气，每 30 分钟更新一次；不准的话在这里选一个城市。'); weather_label.add_theme_font_size_override('font_size',14)
	var row=HBoxContainer.new(); row.add_theme_constant_override('separation',8); settings.add_child(row)
	city_input=LineEdit.new();city_input.placeholder_text='城市，例如 Shanghai';city_input.size_flags_horizontal=Control.SIZE_EXPAND_FILL;row.add_child(city_input)
	button(row,'查找城市',search_city)
	city_options=OptionButton.new();city_options.size_flags_horizontal=Control.SIZE_EXPAND_FILL;settings.add_child(city_options)
	city_options.item_selected.connect(select_city)
	if '--animation-test' in OS.get_cmdline_user_args():button(settings,'打开动画控制面板',func():lab.open())
	# ---- shared dialogs
	file_dialog=FileDialog.new(); file_dialog.access=FileDialog.ACCESS_FILESYSTEM; file_dialog.file_mode=FileDialog.FILE_MODE_OPEN_FILES
	file_dialog.use_native_dialog=true; file_dialog.title='添加到 Lulu 的文件'
	file_dialog.filters=PackedStringArray(['*.txt,*.md,*.pdf,*.docx,*.xlsx,*.csv,*.tsv,*.json,*.html,*.log ; 工作文件']); panel.add_child(file_dialog)
	file_dialog.file_selected.connect(import_file); file_dialog.files_selected.connect(import_files)
	notice_popup=AcceptDialog.new(); notice_popup.title='Lulu'; panel.add_child(notice_popup)
	make_tasks_window()
	var draft=FileAccess.get_file_as_string('user://draft.txt') if FileAccess.file_exists('user://draft.txt') else ''
	prompt.text=draft; prompt.text_changed.connect(func(): var f=FileAccess.open('user://draft.txt',FileAccess.WRITE); if f: f.store_string(prompt.text))

func spacer(height: int) -> Control:
	var c=Control.new(); c.custom_minimum_size=Vector2(0,height); return c

func flat_box(color: Color) -> StyleBoxFlat:
	var box=StyleBoxFlat.new(); box.bg_color=color; box.set_corner_radius_all(10); box.content_margin_left=12; box.content_margin_right=12; box.content_margin_top=8; box.content_margin_bottom=8; return box

func page_title(parent: Node, title: String, hint: String):
	var t=Label.new(); t.text=title; t.add_theme_font_size_override('font_size',20); t.add_theme_color_override('font_color',Color('#5a4b3b')); parent.add_child(t)
	var h=label(parent,hint); h.add_theme_font_size_override('font_size',14); h.add_theme_color_override('font_color',Color('#7d6e5d'))

func make_tasks_window():
	tasks_window=Window.new(); tasks_window.title='Lulu · 没做完的事'; tasks_window.size=Vector2i(640,420); tasks_window.min_size=Vector2i(520,320); tasks_window.close_requested.connect(func(): tasks_window.hide()); add_child(tasks_window); window_background(tasks_window)
	var root=MarginContainer.new(); root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT); tasks_window.add_child(root)
	for edge in ['margin_left','margin_right','margin_top','margin_bottom']: root.add_theme_constant_override(edge,16)
	var col=column(root,'任务'); col.theme=ui_theme()
	label(col,'等你补充或没做完的任务。选中一项，可以继续、补充信息，或看执行记录。').add_theme_font_size_override('font_size',14)
	task_list=list_box(col); task_list.item_activated.connect(func(i): task_result())
	var tr=HBoxContainer.new(); tr.add_theme_constant_override('separation',8); col.add_child(tr)
	button(tr,'继续',resume_task); button(tr,'补充信息',func():open_pending_question()); button(tr,'执行记录',func():if not task_list.get_selected_items().is_empty():show_record(str(tasks[task_list.get_selected_items()[0]].id))); button(tr,'看结果',task_result)
	tasks_window.hide()

func open_tasks_window():
	tasks_window.popup_centered(); tasks_window.grab_focus()

func add_bubble(role: String, text: String):
	var row=HBoxContainer.new(); row.add_theme_constant_override('separation',0); chat_box.add_child(row)
	var mine=role=='user'
	if mine:
		var pad=Control.new(); pad.size_flags_horizontal=Control.SIZE_EXPAND_FILL; pad.size_flags_stretch_ratio=0.25; row.add_child(pad)
	var bubble=PanelContainer.new(); bubble.size_flags_horizontal=Control.SIZE_EXPAND_FILL; bubble.size_flags_stretch_ratio=0.75; row.add_child(bubble)
	var box=StyleBoxFlat.new(); box.bg_color=Color('#efe4cf') if mine else Color('#fdfbf6'); box.border_color=Color('#d9c9a8') if mine else Color('#e2d8c6'); box.set_border_width_all(1); box.set_corner_radius_all(14)
	box.content_margin_left=14; box.content_margin_right=14; box.content_margin_top=10; box.content_margin_bottom=10; bubble.add_theme_stylebox_override('panel',box)
	var inner=VBoxContainer.new(); inner.add_theme_constant_override('separation',4); bubble.add_child(inner)
	var who=Label.new(); who.text='你' if mine else 'Lulu'; who.add_theme_font_size_override('font_size',12); who.add_theme_color_override('font_color',Color('#8a7b69')); inner.add_child(who)
	var body=RichTextLabel.new(); body.bbcode_enabled=false; body.fit_content=true; body.scroll_active=false; body.selection_enabled=true; body.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	body.add_theme_font_size_override('normal_font_size',16); body.add_theme_color_override('default_color',Color('#3d342a')); body.text=text; inner.add_child(body)
	if not mine:
		var pad2=Control.new(); pad2.size_flags_horizontal=Control.SIZE_EXPAND_FILL; pad2.size_flags_stretch_ratio=0.25; row.add_child(pad2)

func clear_bubbles():
	for child in chat_box.get_children():
		if child==welcome: chat_box.remove_child(child)
		else: child.queue_free()

func go_chat():
	tabs.current_tab=0
	if not nav_buttons.is_empty(): nav_buttons[0].button_pressed=true

func make_alert():
	alert=Window.new();alert.title='Lulu 提醒你';alert.size=Vector2i(440,220);alert.always_on_top=true;add_child(alert)
	window_background(alert)
	var col=VBoxContainer.new();col.theme=ui_theme();col.position=Vector2(20,20);col.size=Vector2(400,170);alert.add_child(col)
	alert_label=label(col,'');alert_label.custom_minimum_size=Vector2(0,100)
	button(col,'知道了',dismiss_due)
	alert.close_requested.connect(dismiss_due)
func toggle_reading():
	animation.set_reading(not animation.reading)
func submit():
	if shutting_down or task_active or request_pending: return
	if prompt.text.strip_edges().is_empty():
		if selected_tag().is_empty() or picked_files.is_empty(): notify_text('先说点什么，或者选一个文件。'); return
		var names=[]
		for n in picked_files:names.append(str(n).get_file())
		prompt.text=str(tag_spec(selected_tag()).label)+'：'+'、'.join(names)
	if resume_id.is_empty():animation.agent_mode='';animation.recovered=false
	request_pending=true; run_button.disabled=true; animation.set_agent_status('thinking')
	if session_id.is_empty(): await new_session()
	var payload={'text':prompt.text.strip_edges(),'session':session_id,'resume':resume_id}
	var skill=selected_tag()
	if not skill.is_empty():
		payload['skill']=skill;payload['files']=picked_files.duplicate();payload['options']=collect_options()
	var response=await bridge.request_api(HTTPClient.METHOD_POST,'chat',payload)
	request_pending=false
	if response.has('error'): notify_text(str(response.error)); animation.set_agent_status('blocked'); run_button.disabled=task_active; return
	go_chat(); task_id=str(response.task); task_active=true; started_ms=Time.get_ticks_msec(); prompt.text=''; resume_id=''; animation.set_agent_status('thinking'); previous_status='queued'; cancel_button.disabled=false
	clear_picked_files()
	await load_messages()

func cancel():
	if task_id.is_empty(): return
	cancel_button.disabled=true; notify_text('正在停止，先完成手头的文件操作…')
	var response=await bridge.request_api(HTTPClient.METHOD_POST,'tasks/'+task_id+'/cancel')
	if response.has('error'): notify_text(str(response.error)); cancel_button.disabled=false

func search_city():
	weather_label.text='正在查找城市…'
	var response=await bridge.request_api(HTTPClient.METHOD_POST,'weather/search',{'query':city_input.text})
	if response.has('error'):weather_label.text=str(response.error);return
	cities=response.get('cities',[]);city_options.clear();city_options.add_item('请选择城市')
	for city in cities:city_options.add_item('%s · %s · %s' % [city.name,city.admin1,city.country])
	weather_label.text='请选择搜索结果' if not cities.is_empty() else '未找到城市，请换用英文名称'
func select_city(index: int):
	if index<1 or index>cities.size():return
	var response=await bridge.request_api(HTTPClient.METHOD_POST,'weather/city',cities[index-1])
	weather_label.text=str(response.get('error','城市已保存，正在更新…'))
func dismiss_due():
	if shown_due.is_empty():return
	var response=await bridge.request_api(HTTPClient.METHOD_POST,'reminders',{'action':'ack','id':shown_due})
	if response.has('error'):alert_label.text=str(response.error);return
	shown_due='';alert.hide();animation.acknowledge();poll_time=1
func poll():
	polling=true
	var response=await bridge.request_api(HTTPClient.METHOD_GET,'desktop')
	connected=not response.has('error')
	if not connected:
		notify_text(str(response.error)); animation.set_agent_status('blocked') if task_active else animation.set_agent_status('cancelled'); polling=false; return
	tasks=response.tasks; reminders=response.reminders;questions=response.get('questions',[]);last_artifact=str(response.get('last_artifact',''))
	if not questions.is_empty() and not question_card.visible and question_seen!=str(questions[0].id):open_pending_question()
	var active=false; var selected_status=''
	var selection=task_list.get_selected_items()
	var selected_task=str(task_list.get_item_metadata(selection[0])) if not selection.is_empty() else ''
	task_list.clear()
	for task in tasks:
		var label={'queued':'等待中','running':'处理中','completed':'已完成','failed':'失败','awaiting_input':'等你补充','resumed':'已继续','paused':'未完成，可继续','interrupted':'已中断，可继续','cancelled':'已停止'}.get(task.status,task.status)
		task_list.add_item(str(label)+' · '+str(task.goal).left(75))
		task_list.set_item_metadata(task_list.item_count-1,task.id)
		if str(task.id)==selected_task: task_list.select(task_list.item_count-1)
		if task.status in ['queued','running']:
			active=true
			if task_id!=str(task.id): task_id=str(task.id); session_id=str(task.session); started_ms=Time.get_ticks_msec()
		if str(task.id)==task_id:
			selected_status=str(task.status)
			if task.status in ['queued','running']:animation.set_agent_status(str(task.get('animation','thinking')))
			elif selected_status!=previous_status:
				if selected_status=='completed':animation.set_agent_status('completed')
				elif selected_status=='cancelled':animation.set_agent_status('cancelled')
				elif selected_status in ['failed','paused','interrupted','awaiting_input']:animation.set_agent_status('blocked')
	if active:
		var backend=response.get('backend',{})
		if bool(backend.get('think',false)): notify_text('正在仔细想，可能需要一两分钟 · 已用 '+str((Time.get_ticks_msec()-started_ms)/1000)+' 秒 · 可随时停止')
		else: notify_text('正在处理 · 已用 '+str((Time.get_ticks_msec()-started_ms)/1000)+' 秒 · '+str(backend.get('label',''))+' · 可随时停止')
	if not selected_status.is_empty() and selected_status!=previous_status and not active:
		await load_messages(); refresh_time=10
		notify_text('')
	previous_status=selected_status; task_active=active; run_button.disabled=active or request_pending or shutting_down; cancel_button.disabled=not active
	var pending=0
	for task in tasks:
		if task.status in ['awaiting_input','paused','interrupted']: pending+=1
	pending_button.visible=pending>0; pending_button.text='没做完的（'+str(pending)+'）'
	var reminder_selection=reminder_list.get_selected_items()
	var selected_reminder=str(reminder_list.get_item_metadata(reminder_selection[0])) if not reminder_selection.is_empty() else ''
	reminder_list.clear(); var due=0
	for r in reminders:
		var is_due=float(r.due)<=float(response.now)
		if is_due: due+=1
		reminder_list.add_item(('到时间了 · ' if is_due else '待提醒 · ')+str(r.text))
		reminder_list.set_item_metadata(reminder_list.item_count-1,r.id)
		if str(r.id)==selected_reminder: reminder_list.select(reminder_list.item_count-1)
	if due>0: pet_status.text='有 '+str(due)+' 条提醒到时间了'; panel.title='Lulu · '+str(due)+' 条提醒'
	else: panel.title='Lulu · 你的工作伙伴'
	var scene=await bridge.request_api(HTTPClient.METHOD_GET,'companion')
	if not scene.has('error'):
		var weather=scene.get('weather',{});animation.weather=str(weather.get('condition','unknown'))
		if animation.weather in ['sunny','rainy','cloudy'] and not animation.weather_opened and not lab.active and not shutting_down:animation.play_weather_opening()
		weather_label.text='%s · %s · %s' % [weather.get('city',''),{'sunny':'晴天','rainy':'下雨','cloudy':'阴天','unknown':'天气未就绪'}.get(animation.weather,'未知'),weather.get('detail','')]
		var care=scene.get('care',{}).get('event')
		if care is Dictionary and int(care.id)!=last_care_id and not lab.active and not task_active and not shutting_down and animation.agent_mode=='' and (animation.phase=='idle' or animation.phase.ends_with('_loop')):
			last_care_id=int(care.id);animation.feedback(str(care.action))
			await bridge.request_api(HTTPClient.METHOD_POST,'care/dismiss',{'id':last_care_id})
		due_items=scene.get('due',[])
		if shown_due.is_empty() and not due_items.is_empty() and not shutting_down:
			var item=due_items[0];shown_due=str(item.id);alert_label.text='到时间啦：'+str(item.text)
			alert.show();alert.grab_focus()
	polling=false

func begin_quit():
	if shutting_down:return
	shutting_down=true;quit_button.disabled=true;read_button.disabled=true;run_button.disabled=true
	animation.request_quit()
	if task_active:cancel()
func _notification(what):
	if what==NOTIFICATION_WM_CLOSE_REQUEST:begin_quit()
func _process(delta):
	# Animation time is visual time; never skip a source segment after a stall.
	delta=minf(delta,0.05)
	if animation==null:return
	var show_path=OS.get_environment('LULU_SHOW_PANEL')
	if not show_path.is_empty() and FileAccess.file_exists(show_path):DirAccess.remove_absolute(show_path);show_panel()
	if drag and not Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT):
		if drag_moved:(lab.state if lab.active else animation).end_drag()
		drag=false
	record_poll+=delta
	if record_window!=null and record_window.visible and record_poll>2:
		record_poll=0;refresh_record()
	refresh_time+=delta
	if refresh_time>12 and not refreshing:refresh_time=0;refresh()
	frames.pinned=[str(frames.groups[display_frame])]
	if blend_time<.16:frames.pinned.append(str(frames.groups[blend_from]))
	if lab.active:
		var upcoming=lab.preload_action()
		if not upcoming.is_empty() and not upcoming in frames.recent:frames.ensure(upcoming)
	frames.pump()
	lab.update(delta)
	var current=lab.state if lab.active else animation
	var group=str(frames.groups[current.frame])
	if not group in frames.recent:frames.ensure(group)
	loading=not frames.ready(group)
	if not loading and blend_time>=.16 and (not lab.active or not lab.paused):
		current.advance(delta*(lab.speed if lab.active else 1.0))
	var ready_to_present=lab.settle() if lab.active else true
	if not lab.active and animation.finished:get_tree().quit();return
	group=str(frames.groups[current.frame])
	if not group in frames.recent:frames.ensure(group)
	if frames.ready(group) and ready_to_present and blend_time>=.16:
		if last_display_phase!=current.phase or (current.frame<display_frame and current.phase!='idle'):
			blend_from=display_frame
			# Keep adjacent source slices exact; blend loop seams as well as scene changes.
			# Finish this blend before accepting another target, preventing interrupted fades.
			blend_time=0 if abs(current.frame-display_frame)>1 else 1
			last_display_phase=current.phase
		display_frame=current.frame
	blend_time+=delta
	var phase=current.phase
	pet_status.text='我在，随时叫我'
	if frames_missing:pet_status.text='缺少动画资源包，请重新运行安装脚本'
	elif phase.begins_with('read_'):pet_status.text='安静陪你看书'
	elif phase.ends_with('_loop') or phase=='sleep_enter':pet_status.text='点点我，或拖一下叫醒我～'
	elif phase.ends_with('_exit'):pet_status.text='等一下，我收拾好就来～'
	elif phase=='goodbye':pet_status.text='下次见～'
	elif phase=='ok':pet_status.text='好，提醒记下啦！'
	elif phase.begins_with('sulk'):pet_status.text='哼，快来哄哄我～'
	elif phase in ['enter','work','exit']:pet_status.text='正在帮你处理…'
	if phase.begins_with('thinking'):pet_status.text='让我想想…' if phase!='thinking_done' else '想到啦！'
	elif phase.begins_with('blocked'):pet_status.text='卡住了，打开工作窗口看看'
	elif phase=='resolved':pet_status.text='这次弄明白啦！'
	elif phase in ['complete','complete_alt']:pet_status.text='搞定啦！'
	elif phase.begins_with('candy'):pet_status.text='辛苦啦，点我喂颗糖～'
	elif phase.begins_with('pinch'):pet_status.text='唔，轻一点嘛…'
	elif phase=='night':pet_status.text='夜深啦，记得休息'
	if loading:pet_status.text='稍等一下，马上就好…'
	elif lab.active:pet_status.text='动画测试中'
	read_button.text='收书' if animation.reading else '陪伴'
	poll_time+=delta;diagnostic_time+=delta
	if poll_time>.75 and not polling:poll_time=0;poll()
	if diagnostic_time>1:
		diagnostic_time=0
		var f=FileAccess.open('user://runtime.json',FileAccess.WRITE)
		if f:f.store_string(JSON.stringify({'phase':phase,'frame':display_frame,'reading':animation.reading,'busy':animation.busy,'history':animation.history,'cached_frames':frames.textures.size(),'texture_bytes':frames.cached_bytes,'test_mode':lab.active,'loading':loading}));f.close()
	var shown_blend=minf(blend_time,.16)
	if display_frame!=last_draw_frame or blend_from!=last_draw_from or shown_blend!=last_draw_blend:
		last_draw_frame=display_frame;last_draw_from=blend_from;last_draw_blend=shown_blend
		queue_redraw()
func _draw():
	if frames==null or not frames.textures.has(display_frame):return
	var previous=frames.textures.get(blend_from,frames.textures[display_frame])
	transition_material.set_shader_parameter('previous_texture',previous)
	transition_material.set_shader_parameter('progress',min(1.0,blend_time/.16))
	transition_material.set_shader_parameter('next_rect',frames.texture_rect(display_frame))
	transition_material.set_shader_parameter('previous_rect',frames.texture_rect(blend_from))
	draw_texture_rect(frames.textures[display_frame],Rect2(0,0,528,320),false)
func _gui_input(event):
	var current=lab.state if lab.active else animation
	if event is InputEventMouseButton and event.button_index==MOUSE_BUTTON_LEFT:
		if event.pressed:
			drag=true;drag_moved=false;drag_pointer=DisplayServer.mouse_get_position()
			drag_start=drag_pointer-get_window().position
		else:
			if drag_moved:current.end_drag()
			elif drag:current.interact()
			drag=false
	if event is InputEventMouseMotion and drag:
		if not drag_moved and DisplayServer.mouse_get_position().distance_to(drag_pointer)>6:
			drag_moved=true;current.start_drag()
		if drag_moved:get_window().position=DisplayServer.mouse_get_position()-drag_start

func set_pet_scale(value: float):
	pet_scale=clampf(value,.75,1.5)
	var window=get_window();var bottom_right=window.position+window.size
	window.size=Vector2i(roundi(528*pet_scale),roundi(420*pet_scale))
	window.position=bottom_right-window.size
func show_panel():
	animation.interact(); panel.show(); panel.grab_focus(); go_chat(); prompt.call_deferred('grab_focus')

func column(parent: Node, title: String) -> VBoxContainer:
	var c = VBoxContainer.new(); c.name=title; c.add_theme_constant_override('separation',10); parent.add_child(c); return c

func list_box(parent: Node) -> ItemList:
	var item = ItemList.new(); item.size_flags_vertical=Control.SIZE_EXPAND_FILL; item.custom_minimum_size=Vector2(0,70); parent.add_child(item); return item

func line(parent: Node, placeholder: String) -> LineEdit:
	var input = LineEdit.new(); input.placeholder_text=placeholder; parent.add_child(input); return input

func notify_text(text: String):
	status.text=text

func new_session():
	var response=await bridge.request_api(HTTPClient.METHOD_POST,'sessions')
	if response.has('error'): notify_text(str(response.error)); return
	session_id=str(response.id); task_id=''; resume_id=''; clear_bubbles(); await refresh()

func load_messages():
	if session_id.is_empty(): return
	var expected=session_id
	var response=await bridge.request_api(HTTPClient.METHOD_GET,'sessions/'+session_id)
	if expected!=session_id: return
	if response.has('error'): notify_text(str(response.error)); return
	clear_bubbles()
	var items=response.get('items',[])
	if items.is_empty():
		if welcome.get_parent()==null: chat_box.add_child(welcome)
	for m in items: add_bubble(str(m.role),str(m.content))
	await get_tree().process_frame; await get_tree().process_frame
	chat_scroll.scroll_vertical=100000

func fill_list(list: ItemList, rows: Array[String]):
	# The 12-second refresh used to clear and rebuild every list, dropping whatever the person had just selected.
	# Rebuild only when the rows changed, and put the selection back by text.
	var same=list.item_count==rows.size()
	if same:
		for i in range(rows.size()):
			if list.get_item_text(i)!=rows[i]: same=false; break
	if same: return
	var chosen: Array[String]=[]
	for i in list.get_selected_items(): chosen.append(list.get_item_text(i))
	list.clear()
	for row in rows: list.add_item(row)
	for i in range(rows.size()):
		if rows[i] in chosen: list.select(i,false)
func refresh():
	if refreshing: return
	refreshing=true
	var response=await bridge.request_api(HTTPClient.METHOD_GET,'state')
	if response.has('error'): notify_text(str(response.error)); refreshing=false; return
	workspace=str(response.workspace); memories=response.memories; files=response.files; candidates=response.get('memory_candidates',[])
	var memory_rows: Array[String]=[]
	for m in memories: memory_rows.append(str(m.key)+'：'+str(m.value))
	fill_list(memory_list,memory_rows)
	var candidate_rows: Array[String]=[]
	for c in candidates: candidate_rows.append(str(c.key)+'：'+str(c.value)+'   （原话：'+str(c.quote).left(40)+'）')
	fill_list(candidate_list,candidate_rows)
	candidate_label.text='要记住这些吗？点“记住”后才会保存。' if not candidates.is_empty() else '暂时没有需要确认的记忆'
	var file_rows: Array[String]=[]
	for f in files:
		var ext=str(f.path).get_extension().to_upper()
		var size=float(f.bytes); var size_text=(str(snapped(size/1048576,.1))+' MB') if size>1048576 else (str(snapped(size/1024,.1))+' KB')
		file_rows.append('['+ext+']  '+str(f.path)+'    '+size_text)
	fill_list(file_list,file_rows)
	sessions.clear()
	for item in response.sessions:
		var label='新对话'
		for t in response.tasks:
			if t.session==item.id: label=str(t.goal).left(36); break
		sessions.add_item(label); sessions.set_item_metadata(sessions.item_count-1,item.id)
		if session_id==item.id: sessions.select(sessions.item_count-1)
	if session_id.is_empty() and not response.sessions.is_empty(): session_id=str(response.sessions[0].id); await load_messages()
	var model=response.model
	backend_line=str(model.get('label','模型'))+' · '+str(model.get('model',''))+(' · 深度思考 开' if bool(model.get('think',false)) else '')
	model_pill.text=('● ' if bool(model.get('connected',false)) else '○ ')+str(model.get('label','模型'))+'\n'+str(model.get('model','')).left(28)+('\n深度思考 开' if bool(model.get('think',false)) else '')
	if not task_active:
		var where='本机运行' if str(model.get('backend',''))=='ollama' else str(model.get('label',''))
		if bool(model.get('connected',false)) and bool(model.get('installed',true)): notify_text('')
		elif bool(model.get('connected',false)): notify_text('还需要完成安装。到“模型”页点“检查连接”看看。')
		elif str(model.get('backend',''))=='ollama': notify_text('暂时还不能回答。到“模型”页点“检查连接”看看；文件和记忆仍可管理。')
		else: notify_text('暂时连不上 '+where+'，到“模型”页点“检查连接”看看。')
	# the settings page is loaded when opened and after 应用, never while the person may be editing it (a periodic
	# reload used to snap the backend dropdown back to the saved value under their hands)
	if not backend_loaded: load_backend()
	refreshing=false

func save_memory():
	var r=await bridge.request_api(HTTPClient.METHOD_POST,'memory',{'key':memory_key.text,'value':memory_value.text})
	notify_text(str(r.get('error','记住了'))); await refresh()
func delete_memory():
	if memory_list.get_selected_items().is_empty(): return
	var confirmation=ConfirmationDialog.new(); confirmation.dialog_text='要忘掉这条记忆吗？\n用到过它的那几条对话会一并删除；为保证不再用到，之前的对话也不再作为后面回答的依据（记录还在，只是不参与）。文件不受影响。'; panel.add_child(confirmation)
	var key=str(memories[memory_list.get_selected_items()[0]].key)
	confirmation.confirmed.connect(func():
		var r=await bridge.request_api(HTTPClient.METHOD_DELETE,'memory',{'key':key}); notify_text(str(r.get('error','已删除这条记忆'))); await load_messages(); await refresh(); confirmation.queue_free())
	confirmation.canceled.connect(confirmation.queue_free); confirmation.popup_centered(Vector2i(560,180))
func import_file(path: String):
	var f=FileAccess.open(path,FileAccess.READ)
	if not f: notify_text('这个文件打不开'); return
	if f.get_length()>20*1024*1024: notify_text('单文件上限20MB'); return
	var data=Marshalls.raw_to_base64(f.get_buffer(f.get_length())); f.close()
	var r=await bridge.request_api(HTTPClient.METHOD_POST,'import',{'name':path.get_file(),'content':data})
	notify_text(str(r.get('error','已添加 '+path.get_file()))); await refresh()
func import_files(paths: PackedStringArray):
	for path in paths: await import_file(path)
func open_file():
	if not file_list.get_selected_items().is_empty(): OS.shell_open(workspace.path_join(str(files[file_list.get_selected_items()[0]].path)))
func use_file():
	if file_list.get_selected_items().is_empty(): notify_text('先在列表里选一个文件。'); return
	picked_files=[]
	for i in file_list.get_selected_items():picked_files.append(str(files[i].path))
	update_file_chip(); go_chat(); prompt.grab_focus(); notify_text('已选好文件，点一个标签再打字，或者直接说要做什么。')
func resolve_candidate(accept: bool):
	if candidate_list.get_selected_items().is_empty(): notify_text('先选一条要确认的记忆。'); return
	var c=candidates[candidate_list.get_selected_items()[0]]
	var r=await bridge.request_api(HTTPClient.METHOD_POST,'memory/candidates/'+str(c.id),{'action':'accept' if accept else 'reject'})
	notify_text(str(r.get('error','记住了：'+str(c.key) if accept else '好，忽略这条。'))); await refresh()
func parse_reminder():
	var text=reminder_phrase.text.strip_edges()
	if text.is_empty(): return
	var r=await bridge.request_api(HTTPClient.METHOD_POST,'reminders',{'action':'parse','text':text})
	if r.has('error'): notify_text(str(r.error)); return
	notify_text('好，'+str(r.get('when',''))+'提醒你'+str(r.get('text',''))); reminder_phrase.text=''; animation.acknowledge(); poll_time=1
func task_result():
	if task_list.get_selected_items().is_empty(): return
	var t=tasks[task_list.get_selected_items()[0]]; notice_popup.dialog_text=str(t.goal)+'\n\n'+str(t.answer); notice_popup.popup_centered(Vector2i(650,350))
func resume_task():
	if task_list.get_selected_items().is_empty(): return
	var selected=tasks[task_list.get_selected_items()[0]]
	if str(selected.status)=='awaiting_input':open_pending_question(str(selected.id));return
	var t=selected; resume_id=str(t.id); session_id=str(t.session); prompt.text='继续这个任务，先核对已经完成的步骤，避免重复执行。'; tasks_window.hide(); go_chat(); load_messages()
	animation.recovered=true
func ack_reminder():
	if reminder_list.get_selected_items().is_empty(): return
	var r=reminders[reminder_list.get_selected_items()[0]]
	await bridge.request_api(HTTPClient.METHOD_POST,'reminders',{'action':'ack' if float(r.due)<=Time.get_unix_time_from_system() else 'cancel','id':r.id})

	animation.acknowledge()
func capture_preview():
	await get_tree().create_timer(3).timeout
	await RenderingServer.frame_post_draw
	var folder=OS.get_environment('LULU_CAPTURE')
	DirAccess.make_dir_recursive_absolute(folder)
	panel.get_texture().get_image().save_png(folder.path_join('panel.png'))
	get_viewport().get_texture().get_image().save_png(folder.path_join('pet.png'))
	var info={'panel_window':panel.get_window_id(),'pet_window':get_window().get_window_id(),'pet_transparent':get_viewport().transparent_bg,'panel_transparent':panel.transparent,'connected':connected,
		'frames_missing':frames_missing,'frames_loaded':frames.textures.size(),'executable':OS.get_executable_path(),'version':Engine.get_version_info().string}
	var f=FileAccess.open(folder.path_join('windows.json'),FileAccess.WRITE)
	if f: f.store_string(JSON.stringify(info))
	if not OS.get_environment('LULU_CAPTURE_QUIT').is_empty(): get_tree().quit()

func make_agent_dialogs():
	record_window=Window.new();record_window.title='Lulu · 执行记录';record_window.size=Vector2i(760,540);record_window.min_size=Vector2i(600,420);record_window.close_requested.connect(func():record_window.hide());add_child(record_window);window_background(record_window)
	var root=MarginContainer.new();root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);record_window.add_child(root)
	for edge in ['margin_left','margin_right','margin_top','margin_bottom']:root.add_theme_constant_override(edge,18)
	var col=column(root,'记录');col.theme=ui_theme()
	label(col,'做了哪些步骤、哪里没成功，都能在这里看。')
	record_body=TextEdit.new();record_body.editable=false;record_body.wrap_mode=TextEdit.LINE_WRAPPING_BOUNDARY;record_body.size_flags_vertical=Control.SIZE_EXPAND_FILL;col.add_child(record_body)
	button(col,'刷新记录',refresh_record);record_window.hide()
	# 补充一下: a card inside the work window, right above the composer (one window, not a second one popping up)
	question_card=PanelContainer.new();var card_box=StyleBoxFlat.new();card_box.bg_color=Color('#fbf3e2');card_box.border_color=Color('#d9b978');card_box.set_border_width_all(1);card_box.set_corner_radius_all(16)
	card_box.content_margin_left=14;card_box.content_margin_right=14;card_box.content_margin_top=10;card_box.content_margin_bottom=10;question_card.add_theme_stylebox_override('panel',card_box)
	composer.get_parent().add_child(question_card);composer.get_parent().move_child(question_card,composer.get_index())
	col=column(question_card,'补充');col.add_theme_constant_override('separation',8)
	question_body=Label.new();question_body.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;question_body.add_theme_font_size_override('font_size',16);col.add_child(question_body)
	question_options=HBoxContainer.new();question_options.add_theme_constant_override('separation',6);col.add_child(question_options)
	question_reply=TextEdit.new();question_reply.custom_minimum_size=Vector2(0,64);question_reply.wrap_mode=TextEdit.LINE_WRAPPING_BOUNDARY;question_reply.placeholder_text='选上面的选项，或直接回答。要用文件的话，先在文件页添加，再告诉我文件名。';col.add_child(question_reply)
	var row=HBoxContainer.new();row.add_theme_constant_override('separation',8);col.add_child(row);question_send=button(row,'回复并继续',answer_pending_question);button(row,'稍后再说',func():question_card.hide());button(row,'取消任务',cancel_pending_question);question_card.hide()

func open_pending_question(for_task: String=''):
	for q in questions:
		if not for_task.is_empty() and str(q.task)!=for_task:continue
		if question_id!=str(q.id):question_reply.text=''
		question_id=str(q.id);question_seen=question_id;question_body.text=str(q.reason)+'\n\n'+str(q.question);question_send.disabled=false
		for child in question_options.get_children(): child.queue_free()
		var options=JSON.parse_string(str(q.get('options','[]')))
		if options is Array:
			for option in options:
				var text=str(option)
				button(question_options,text,func(): question_reply.text=text; answer_pending_question())
		question_card.show();panel.show();go_chat();question_reply.grab_focus();return
	notify_text('暂时没有需要你回答的问题。')

func answer_pending_question():
	if question_id.is_empty() or question_reply.text.strip_edges().is_empty():return
	question_send.disabled=true
	var r=await bridge.request_api(HTTPClient.METHOD_POST,'questions/'+question_id+'/answer',{'answer':question_reply.text.strip_edges()})
	question_send.disabled=false
	if r.has('error'):question_body.text=str(r.error);return
	session_id=str(r.session);task_id=str(r.task);previous_status='queued';task_active=true;animation.recovered=true;animation.set_agent_status('thinking');started_ms=Time.get_ticks_msec();question_card.hide();await load_messages();poll_time=1

func cancel_pending_question():
	if question_id.is_empty():return
	var r=await bridge.request_api(HTTPClient.METHOD_POST,'questions/'+question_id+'/answer',{'action':'cancel'})
	if r.has('error'):question_body.text=str(r.error);return
	question_card.hide();animation.set_agent_status('cancelled');poll_time=1

func show_record(target: String=''):
	record_task=target if not target.is_empty() else task_id
	if record_task.is_empty():
		for t in tasks:
			if str(t.session)==session_id:record_task=str(t.id);break
	if record_task.is_empty():notify_text('这段对话还没有执行记录。');return
	record_window.popup_centered();record_window.grab_focus();await refresh_record()

func refresh_record():
	if record_task.is_empty() or record_refreshing:return
	record_refreshing=true
	var expected=record_task
	var r=await bridge.request_api(HTTPClient.METHOD_GET,'tasks/'+record_task)
	record_refreshing=false
	if expected!=record_task:return
	if r.has('error'):record_body.text=str(r.error);return
	var t=r.task
	var text='任务：'+str(t.goal)+'\n状态：'+str({'awaiting_input':'等你补充','running':'处理中','queued':'等待中','completed':'已完成','paused':'未完成，可继续','failed':'失败','cancelled':'已停止','resumed':'已继续','interrupted':'已中断，可继续'}.get(t.status,t.status))+'\n\n'
	var labels={'template_default_applied':'采用默认模板结构','memory_used':'查看相关记忆','thinking':'仔细思考中','drafting':'正在起草','draft_result':'已收到草稿','draft_retry':'根据已有资料重写','generate_retry':'检查发现问题，正在修改','summary_retry':'摘要与原文不一致，正在修改','tool_started':'开始操作','tool_done':'已收到操作结果','tool_failed':'操作未完成','artifact_verified':'已确认文件可以读取','harness_tool_failed':'操作失败','skill_started':'开始处理','skill_failed':'这一步没能完成','intent':'确认要做的事','plan':'安排处理步骤','history_attached':'参考之前的处理记录','research_started':'开始上网查找','search_started':'正在搜索','search_results':'已收到搜索结果','pages_fetched':'正在读取网页','facts_verified':'正在核对来源','research_result':'本次网上查找结束','answer_regrounded':'已按资料重写，去掉未核实的数字','memory_saved':'已记住','memory_forgotten':'已忘掉这条记忆','memory_candidates':'发现可能值得记住的内容，等你确认','note_saved':'已保存笔记','step_reused':'沿用已完成的部分','model_error':'暂时无法获取回答','error':'处理时出了点问题','finished':'本次处理结束','user_input_required':'等你补充信息','user_input_answered':'收到补充，继续处理','user_input_cancelled':'已取消这个任务','network_evidence':'已获取网上资料','evidence_collected':'正在读取参考资料','gather_failed':'没能读取这份资料','translate_started':'开始翻译','translate_retry':'译文可能有遗漏或数字出错，正在重译','materials_missing':'缺少材料，先请你补充','answer_unverified':'未找到可核实资料，回答仅供参考','follow_up':'按你的修改继续处理','rewrite_started':'开始改写','rewrite_retry':'改写结果与原文有出入，正在重做','ask_file_unverified':'答案在文件里没找到原话依据','extract_started':'开始整理表格'}
	for event in r.get('events',[]):
		var kind=str(event.kind)
		if not labels.has(kind):continue
		var detail=JSON.parse_string(str(event.detail))
		text+=str(labels[kind])
		if detail is Dictionary:
			if detail.has('think') and bool(detail.think):text+='（深度思考）'
			if detail.has('provider'):text+='  · 搜索：'+str(detail.provider)
			for key in ['label','skill','tool','path','error','reason','question','answer','stop_reason','queries','count','engine','key','status','target','problems']:
				if detail.has(key):
					var value=str(detail[key])
					if key=='tool':value=str({'generate_document':'起草并生成文档','create_document':'保存文档','read_document':'读取文档','search':'搜索资料','file':'处理文件','document':'处理文档','save_memory':'保存长期记忆','ask_user':'请求补充信息'}.get(value,value))
					if key=='stop_reason':value=str({'completed':'正常结束','error':'执行中断','cancelled':'已取消'}.get(value,value))
					text+='\n  '+value.left(1800)
			if detail.has('arguments') and detail.arguments is Dictionary:
				for key in ['path','destination','query']:
					if detail.arguments.has(key):text+='\n  '+str(detail.arguments[key]).left(500)
		text+='\n\n'
	text+='结果：'+str(t.answer)
	var scroll=record_body.scroll_vertical
	record_body.text=text
	record_body.scroll_vertical=scroll

# ------------------------------------------------------------- 模型 page
func make_backend_tab(parent: Node):
	backend_tab=column(parent,'模型')
	var tab=backend_tab
	var t=Label.new(); t.text='模型'; t.add_theme_font_size_override('font_size',18); tab.add_child(t)
	label(tab,'在这里选择 Lulu 用什么来回答。本地模型在你的电脑上运行；使用 API 或命令行时，资料是否发送到外部，取决于所选服务和工具。密钥只保存在本机。').add_theme_font_size_override('font_size',14)
	backend_status=label(tab,'正在读取模型设置…');backend_status.add_theme_font_size_override('font_size',14)
	var top=HBoxContainer.new();top.add_theme_constant_override('separation',8);tab.add_child(top)
	backend_option=OptionButton.new();backend_option.size_flags_horizontal=Control.SIZE_EXPAND_FILL;top.add_child(backend_option)
	for name in BACKEND_NAMES:backend_option.add_item(name)
	backend_option.item_selected.connect(func(i):show_backend_boxes(i))
	think_switch=CheckButton.new();think_switch.text='深度思考';think_switch.tooltip_text='总结、写文档、翻译和聊天时多想一会儿再回答。使用本地 4B/8B 模型时，可能需要一两分钟。';top.add_child(think_switch)
	think_switch.toggled.connect(func(on):toggle_think(on))
	button(top,'检查连接',probe_backend);button(top,'测试回答',test_backend)
	local_box=VBoxContainer.new();local_box.add_theme_constant_override('separation',6);tab.add_child(local_box)
	var lr=HBoxContainer.new();local_box.add_child(lr)
	label(lr,'档位').custom_minimum_size=Vector2(60,0)
	tier_option=OptionButton.new();tier_option.size_flags_horizontal=Control.SIZE_EXPAND_FILL;lr.add_child(tier_option)
	for name in TIER_NAMES:tier_option.add_item(name)
	label(local_box,'4B 档使用两个模型，分别负责直接回答和深度思考；8B 档使用一个模型，通过开关切换。缺少模型时，点“检查连接”查看要下载哪一个。').add_theme_font_size_override('font_size',14)
	api_box=VBoxContainer.new();api_box.add_theme_constant_override('separation',6);tab.add_child(api_box)
	var pr=HBoxContainer.new();api_box.add_child(pr)
	label(pr,'服务商').custom_minimum_size=Vector2(60,0)
	preset_option=OptionButton.new();preset_option.size_flags_horizontal=Control.SIZE_EXPAND_FILL;pr.add_child(preset_option)
	for name in PRESET_NAMES:preset_option.add_item(name)
	preset_option.item_selected.connect(func(i):apply_preset(i))
	var ar=HBoxContainer.new();api_box.add_child(ar)
	api_base=LineEdit.new();api_base.placeholder_text='API 地址，例如 https://dashscope.aliyuncs.com/compatible-mode/v1';api_base.size_flags_horizontal=Control.SIZE_EXPAND_FILL;ar.add_child(api_base)
	api_model=LineEdit.new();api_model.placeholder_text='模型名称，例如 qwen-plus';api_model.custom_minimum_size=Vector2(200,0);ar.add_child(api_model)
	var kr=HBoxContainer.new();api_box.add_child(kr)
	api_key=LineEdit.new();api_key.placeholder_text='API 密钥，仅保存在本机 secrets.json';api_key.secret=true;api_key.size_flags_horizontal=Control.SIZE_EXPAND_FILL;kr.add_child(api_key)
	button(kr,'保存密钥',func():save_secret('api_key',api_key))
	claude_box=VBoxContainer.new();claude_box.add_theme_constant_override('separation',6);tab.add_child(claude_box)
	var cr=HBoxContainer.new();claude_box.add_child(cr)
	claude_command=LineEdit.new();claude_command.placeholder_text='Claude 命令，默认 claude；请先登录';claude_command.size_flags_horizontal=Control.SIZE_EXPAND_FILL;cr.add_child(claude_command)
	claude_model=LineEdit.new();claude_model.placeholder_text='模型（可留空）';claude_model.custom_minimum_size=Vector2(200,0);cr.add_child(claude_model)
	label(claude_box,'先在这台电脑上安装 Claude Code 并登录。Lulu 会通过 claude -p 发送请求并获取回答。').add_theme_font_size_override('font_size',14)
	cli_box=VBoxContainer.new();cli_box.add_theme_constant_override('separation',6);tab.add_child(cli_box)
	cli_command=LineEdit.new();cli_command.placeholder_text='输入命令。{output_file} 表示答复文件，{prompt} 表示提示词；省略 {prompt} 时，提示词会加在命令末尾。';cli_box.add_child(cli_command)
	label(cli_box,'默认使用 codex exec。请先确认命令能在终端运行；Lulu 会从 {output_file} 或标准输出读取回答。').add_theme_font_size_override('font_size',14)
	var sr=HBoxContainer.new();sr.add_theme_constant_override('separation',8);tab.add_child(sr)
	label(sr,'联网搜索').custom_minimum_size=Vector2(70,0)
	search_option=OptionButton.new();search_option.custom_minimum_size=Vector2(220,0);sr.add_child(search_option)
	for name in SEARCH_NAMES:search_option.add_item(name)
	search_key=LineEdit.new();search_key.placeholder_text='输入所选搜索服务的密钥';search_key.secret=true;search_key.size_flags_horizontal=Control.SIZE_EXPAND_FILL;sr.add_child(search_key)
	button(sr,'保存搜索密钥',save_search_secret)
	var br=HBoxContainer.new();tab.add_child(br)
	button(br,'应用设置',apply_backend)
	var hint=label(br,'切换服务会在当前任务结束后生效；深度思考开关可随时调整。');hint.add_theme_font_size_override('font_size',14);hint.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	backend_body=TextEdit.new();backend_body.editable=false;backend_body.wrap_mode=TextEdit.LINE_WRAPPING_BOUNDARY;backend_body.size_flags_vertical=Control.SIZE_EXPAND_FILL;backend_body.custom_minimum_size=Vector2(0,120)
	backend_body.placeholder_text='点“检查连接”看看哪些方式可用；点“测试回答”试试当前设置。';tab.add_child(backend_body)
	show_backend_boxes(0)

func show_backend_boxes(index: int):
	local_box.visible=index==0;api_box.visible=index==1;claude_box.visible=index==2;cli_box.visible=index==3

func apply_preset(index: int):
	var key=PRESET_KEYS[index]
	var presets=backend_info.get('options',{}).get('api_presets',{})
	if presets.has(key):
		api_base.text=str(presets[key].get('base',''));api_model.text=str(presets[key].get('model',''))

func describe_backend(info: Dictionary) -> String:
	var lines=[]
	var thinking_model=str(info.get('thinking_model',''))
	var pair=('（深度思考用 '+thinking_model+'）') if thinking_model!=str(info.get('model','')) else ''
	lines.append('当前服务：'+str(info.get('label',''))+' · 模型：'+str(info.get('model',''))+pair)
	var state='已连接' if bool(info.get('connected',false)) else '未连接'
	if bool(info.get('connected',false)) and info.has('installed') and not bool(info.get('installed',true)):state='已连接，模型未安装'
	var speed=info.get('speed',{})
	var tps=float(speed.get('generate_tps',0)) if speed is Dictionary else 0.0
	var speed_text=(' · 实测 '+str(snapped(tps,.1))+' 字/秒') if tps>0 else ''
	lines.append('连接状态：'+state+speed_text+(' · 深度思考：开' if bool(info.get('think',false)) else ' · 深度思考：关'))
	lines.append(('⚠ 资料会发送到外部：' if bool(info.get('leaves_device',false)) else '✓ 资料在本机处理：')+str(info.get('note','')))
	var err=str(info.get('last_error',''))
	if not err.is_empty():lines.append('最近一次错误：'+err.left(160))
	var search=info.get('search',{})
	if search is Dictionary and search.has('detail'):lines.append('联网搜索：'+str(search.detail))
	return '\n'.join(lines)

func load_backend():
	if backend_busy:return
	backend_busy=true
	var info=await bridge.request_api(HTTPClient.METHOD_GET,'backend')
	backend_busy=false
	if info.has('error'):backend_status.text=str(info.error);return
	backend_info=info;backend_loaded=true
	backend_status.text=describe_backend(info)
	var backend=str(info.get('backend','ollama'))
	if backend in BACKEND_KEYS:backend_option.select(BACKEND_KEYS.find(backend));show_backend_boxes(BACKEND_KEYS.find(backend))
	var tier=str(info.get('tier','auto'))
	if tier in TIER_KEYS:tier_option.select(TIER_KEYS.find(tier))
	var preset=str(info.get('api_preset','custom'))
	preset_option.select(PRESET_KEYS.find(preset) if preset in PRESET_KEYS else PRESET_KEYS.size()-1)
	if not api_base.has_focus():api_base.text=str(info.get('api_base',''))
	if backend=='api' and not api_model.has_focus():api_model.text=str(info.get('model',''))
	var keys=info.get('keys',{})
	api_key.placeholder_text=('已保存：'+str(keys.api_key)+'。粘贴新密钥可替换。') if keys is Dictionary and keys.has('api_key') else 'API 密钥，仅保存在本机 secrets.json'
	var provider=str(info.get('search_provider','auto'))
	if provider in SEARCH_KEYS:search_option.select(SEARCH_KEYS.find(provider))
	var saved_search=[]
	if keys is Dictionary:
		for name in SEARCH_SECRETS.values():
			if keys.has(name):saved_search.append(name.replace('_key',''))
	search_key.placeholder_text=('已保存：'+'、'.join(saved_search)+'。粘贴新密钥可替换。') if not saved_search.is_empty() else '输入所选搜索服务的密钥'
	if backend=='claude_cli' and not claude_command.has_focus():claude_command.text=str(info.get('command','')).split(' -p')[0]
	if backend=='cli' and not cli_command.has_focus():cli_command.text=str(info.get('command',''))
	think_switch.set_pressed_no_signal(bool(info.get('think',false)))

func toggle_think(on: bool):
	var r=await bridge.request_api(HTTPClient.METHOD_POST,'backend',{'think':on})
	if r.has('error'):notify_text(str(r.error));think_switch.set_pressed_no_signal(not on);return
	backend_info=r;backend_status.text=describe_backend(r)
	notify_text('已开启深度思考。总结、写文档、翻译和聊天会多想一会儿，回答也会慢一些。' if on else '已关闭深度思考，直接回答。')
	refresh_time=100

func apply_backend():
	var index=backend_option.selected
	var payload={'backend':BACKEND_KEYS[index],'search':{'provider':SEARCH_KEYS[search_option.selected]}}
	if index==0:payload['tier']=TIER_KEYS[tier_option.selected]
	elif index==1:
		var preset=PRESET_KEYS[preset_option.selected]
		payload['api']={'preset':preset,'base':api_base.text.strip_edges(),'model':api_model.text.strip_edges()}
	elif index==2:
		var command=claude_command.text.strip_edges()
		payload['claude_cli']={'command':command if not command.is_empty() else 'claude','model':claude_model.text.strip_edges()}
	else:payload['cli']={'command':cli_command.text.strip_edges()}
	notify_text('正在切换服务…')
	var r=await bridge.request_api(HTTPClient.METHOD_POST,'backend',payload)
	if r.has('error'):notify_text(str(r.error));backend_body.text=str(r.error);return
	backend_info=r;backend_status.text=describe_backend(r)
	notify_text('已切换到 '+str(r.get('label',''))+' · '+str(r.get('model','')))
	backend_body.text='设置已应用。'+(('\n⚠ 请注意：'+str(r.get('note',''))) if bool(r.get('leaves_device',false)) else '')
	refresh_time=100

func save_secret(name: String, field: LineEdit):
	var value=field.text.strip_edges()
	if value.is_empty():notify_text('先粘贴密钥。');return
	var r=await bridge.request_api(HTTPClient.METHOD_POST,'backend/secret',{'name':name,'value':value})
	if r.has('error'):notify_text(str(r.error));return
	field.text='';notify_text('密钥已保存在本机。');await load_backend()

func save_search_secret():
	var provider=SEARCH_KEYS[search_option.selected]
	if not SEARCH_SECRETS.has(provider):notify_text('先选博查、Tavily 或 Brave，再保存对应的密钥。');return
	await save_secret(SEARCH_SECRETS[provider],search_key)
	var r=await bridge.request_api(HTTPClient.METHOD_POST,'backend',{'search':{'provider':provider}})
	if not r.has('error'):backend_info=r;backend_status.text=describe_backend(r)

func probe_backend():
	backend_body.text='正在检查四种连接方式，可能需要几秒钟…'
	var r=await bridge.request_api(HTTPClient.METHOD_POST,'backend/probe',{})
	if r.has('error'):backend_body.text=str(r.error);return
	backend_body.text=str(r.get('summary',''))
	await load_backend()

func test_backend():
	backend_body.text='正在测试回答…'+('深度思考已开启，可能需要多等一会儿。' if think_switch.button_pressed else '')
	var r=await bridge.request_api(HTTPClient.METHOD_POST,'backend/test',{'think':think_switch.button_pressed})
	if r.has('error'):backend_body.text=str(r.error);return
	var text=('✓ 已收到回答' if bool(r.get('ok',false)) else '✗ 测试失败')+' · '+str(r.get('model',''))+' · 用时 '+str(r.get('seconds',''))+' 秒'
	if int(r.get('thinking_chars',0))>0:text+=' · 思考内容 '+str(int(r.get('thinking_chars',0)))+' 字（已隐藏）'
	backend_body.text=text+'\n'+str(r.get('content',''))
	await load_backend()

# ------------------------------------------------------------- 标签行
func make_tag_row(parent: Node):
	tag_group=ButtonGroup.new();tag_group.allow_unpress=true
	tag_row=HFlowContainer.new();tag_row.add_theme_constant_override('h_separation',6);tag_row.add_theme_constant_override('v_separation',6);parent.add_child(tag_row)
	for tag in TAGS:
		var b=Button.new();b.text=str(tag.label);b.toggle_mode=true;b.button_group=tag_group;b.add_theme_font_size_override('font_size',14)
		b.size_flags_vertical=Control.SIZE_SHRINK_CENTER;b.size_flags_horizontal=Control.SIZE_SHRINK_BEGIN
		b.toggled.connect(func(on):on_tag_toggled(str(tag.key),on))
		tag_row.add_child(b);tag_buttons[str(tag.key)]=b
	file_chip=Button.new();file_chip.text='选文件…';file_chip.add_theme_font_size_override('font_size',14);file_chip.size_flags_vertical=Control.SIZE_SHRINK_CENTER;file_chip.pressed.connect(open_file_picker);tag_row.add_child(file_chip)
	option_row=HBoxContainer.new();option_row.add_theme_constant_override('separation',8);parent.add_child(option_row);option_row.visible=false
	make_file_picker()

func selected_tag() -> String:
	for key in tag_buttons:
		if tag_buttons[key].button_pressed:return str(key)
	return ''

func tag_spec(key: String) -> Dictionary:
	for tag in TAGS:
		if str(tag.key)==key:return tag
	return {}

func on_tag_toggled(key: String, on: bool):
	if not on and selected_tag()!='':return
	for child in option_row.get_children():child.queue_free()
	option_widgets={};columns_input=null
	var spec=tag_spec(key) if on else {}
	if spec.is_empty():
		option_row.visible=false;composer_hint.text=DEFAULT_HINT;prompt.placeholder_text='输入你想做的事，或和 Lulu 聊聊…';return
	composer_hint.text=str(spec.hint);prompt.placeholder_text=str(spec.hint)
	for name in spec.options:
		if name=='columns':
			plain_label(option_row,'表里放什么')
			columns_input=LineEdit.new();columns_input.placeholder_text='用顿号隔开，例如 姓名、电话、金额';columns_input.size_flags_horizontal=Control.SIZE_EXPAND_FILL;columns_input.size_flags_vertical=Control.SIZE_SHRINK_CENTER;option_row.add_child(columns_input)
			var preset=OptionButton.new();preset.size_flags_vertical=Control.SIZE_SHRINK_CENTER;preset.add_item('常用列…')
			for c in ['姓名','电话','邮箱','日期','金额','负责人','公司','地址']:preset.add_item(c)
			preset.item_selected.connect(func(i):
				if i>0:
					var c=preset.get_item_text(i);var cur=columns_input.text.strip_edges()
					columns_input.text=c if cur.is_empty() else cur+'、'+c
					preset.select(0))
			option_row.add_child(preset)
			continue
		var set=OPTION_SETS[name]
		plain_label(option_row,str(set.label))
		var ob=OptionButton.new();ob.size_flags_vertical=Control.SIZE_SHRINK_CENTER
		for v in set['values']:ob.add_item(str(v))
		option_row.add_child(ob);option_widgets[str(set.key)]=ob
	option_row.visible=option_row.get_child_count()>0
	prompt.grab_focus()

func collect_options() -> Dictionary:
	var out={}
	for key in option_widgets:
		var ob=option_widgets[key]
		var v=ob.get_item_text(ob.selected)
		if v!='自动判断' and v!='直接显示':out[key]=v
	if columns_input!=null and not columns_input.text.strip_edges().is_empty():
		var cols=[]
		for c in columns_input.text.replace('，','、').replace(',','、').replace(' ','、').split('、'):
			if not c.strip_edges().is_empty():cols.append(c.strip_edges())
		out['columns']=cols
	return out

func make_file_picker():
	file_picker=Window.new();file_picker.title='选文件';file_picker.size=Vector2i(520,420);file_picker.min_size=Vector2i(420,320);file_picker.close_requested.connect(func():file_picker.hide());add_child(file_picker);window_background(file_picker)
	var root=MarginContainer.new();root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);file_picker.add_child(root)
	for edge in ['margin_left','margin_right','margin_top','margin_bottom']:root.add_theme_constant_override(edge,16)
	var col=column(root,'选文件');col.theme=ui_theme()
	label(col,'点选要用的文件，可以多选。').add_theme_font_size_override('font_size',13)
	picker_list=list_box(col);picker_list.select_mode=ItemList.SELECT_MULTI
	picker_list.item_activated.connect(func(_i):confirm_file_picker())
	var row=HBoxContainer.new();col.add_child(row)
	button(row,'就用这些',confirm_file_picker);button(row,'添加文件…',func():file_dialog.popup_centered_ratio(.75));button(row,'取消',func():file_picker.hide())
	file_picker.hide()

func open_file_picker():
	picker_list.clear()
	if not last_artifact.is_empty():
		picker_list.add_item('刚生成的文件 · '+last_artifact);picker_list.set_item_metadata(0,last_artifact)
	for f in files:
		picker_list.add_item('['+str(f.path).get_extension().to_upper()+']  '+str(f.path));picker_list.set_item_metadata(picker_list.item_count-1,str(f.path))
	if picker_list.item_count==0:notify_text('这里还没有文件，先点“添加文件…”');file_dialog.popup_centered_ratio(.75);return
	for i in range(picker_list.item_count):
		if str(picker_list.get_item_metadata(i)) in picked_files:picker_list.select(i,false)
	file_picker.popup_centered();file_picker.grab_focus()

func confirm_file_picker():
	picked_files=[]
	for i in picker_list.get_selected_items():
		var name=str(picker_list.get_item_metadata(i))
		if not name in picked_files:picked_files.append(name)
	file_picker.hide();update_file_chip()

func update_file_chip():
	if picked_files.is_empty():file_chip.text='选文件…';return
	var names=[]
	for n in picked_files:names.append(str(n).get_file())
	file_chip.text='已选：'+'、'.join(names).left(40)+'  ×'

func clear_picked_files():
	picked_files=[];update_file_chip()

