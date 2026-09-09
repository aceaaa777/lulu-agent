extends Window
const State=preload('res://src/animation_state.gd')
const ACTIONS=[['站立','idle'],['左右看 A','look_a'],['左右看 B','look_b'],['眨眼','blink'],['睡觉 · 长版','sleep'],['睡觉 · 短版','sleep_alt'],['晴天','sunny'],['下雨','rainy'],['阴天','cloudy'],['看书陪伴','read'],['看书备选','read_alt'],['处理任务','task'],['挥手','wave'],['赌气','sulk'],['提醒 OK','ok'],['退出挥手','goodbye'],['拖动 · 捏脸','pinch'],['久坐 · 喂糖','candy'],['喂糖 · 近景备选','candy_close'],['夜晚 · 黑眼圈','night'],['Agent 思考中','thinking'],['思考完成','thinking_done'],['目标不清 / 卡住','blocked'],['补充后理清','resolved'],['任务完成 · 搞定','complete'],['任务完成 · done','complete_alt']]
var host
var state
var active=false
var paused=false
var speed=1.0
var selected='idle'
var pending_action=''
var automatic=false
var sequence_index=0
var held_time=0.0
var idle_time=0.0
var info: Label
var scrub: HSlider
var pause_button: Button
var updating=false
var max_delta=0.0
var reference_preview: TextureRect
var motion_preview: TextureRect
var preview_panels: Array[PanelContainer]=[]
var inspection_background=Color.BLACK
var desktop_backdrop: ColorRect
func _init(owner_node):host=owner_node
func _ready():
	title='Lulu · 动画控制面板';size=Vector2i(700,780);min_size=Vector2i(660,580)
	host.window_background(self)
	var scroll=ScrollContainer.new();scroll.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);add_child(scroll)
	var margin=MarginContainer.new();margin.size_flags_horizontal=Control.SIZE_EXPAND_FILL;scroll.add_child(margin)
	for key in ['margin_left','margin_right','margin_top','margin_bottom']:margin.add_theme_constant_override(key,20)
	var col=VBoxContainer.new();col.theme=host.ui_theme();col.size_flags_horizontal=Control.SIZE_EXPAND_FILL;col.add_theme_constant_override('separation',12);margin.add_child(col)
	host.label(col,'动画衔接测试').add_theme_font_size_override('font_size',24)
	host.label(col,'桌面的 Lulu 实时预览。切换先完成收尾；天气一次点按完整播放；退出挥手只演示。')
	var grid=GridContainer.new();grid.columns=4;col.add_child(grid)
	for item in ACTIONS:
		var action=str(item[1]);host.button(grid,str(item[0]),func():choose(action))
	var row=HBoxContainer.new();col.add_child(row)
	pause_button=host.button(row,'暂停',func():paused=not paused;pause_button.text='继续' if paused else '暂停')
	host.button(row,'前进一帧',func():paused=true;pause_button.text='继续';if_ready_step())
	host.button(row,'点击 / 拖动唤醒',func():automatic=false;state.interact())
	host.button(row,'吃糖 / 已补充',func():automatic=false;resolve_feedback())
	host.button(row,'结束当前动作',func():automatic=false;release_current())
	row=HBoxContainer.new();col.add_child(row)
	host.button(row,'连续测试全部',start_sequence)
	host.button(row,'重新播放',func():choose(selected))
	host.button(row,'回到正常陪伴',leave)
	row=HBoxContainer.new();col.add_child(row);var speed_label=host.label(row,'播放速度');speed_label.autowrap_mode=TextServer.AUTOWRAP_OFF
	var speeds=OptionButton.new();row.add_child(speeds)
	for value in ['0.25× 慢放','0.5× 慢放','1× 正常','2× 快放']:speeds.add_item(value)
	speeds.select(2);speeds.item_selected.connect(func(i):speed=[.25,.5,1.0,2.0][i])
	host.button(row,'重置帧耗时',func():max_delta=0)
	row=HBoxContainer.new();col.add_child(row)
	var size_label=host.label(row,'桌宠整体大小');size_label.autowrap_mode=TextServer.AUTOWRAP_OFF
	var sizes=OptionButton.new();row.add_child(sizes)
	for title in ['75%','100%','125%','150%']:sizes.add_item(title)
	sizes.select(1);sizes.item_selected.connect(func(i):host.set_pet_scale([.75,1.0,1.25,1.5][i]))
	var comparison=VBoxContainer.new();comparison.visible=true;col.add_child(comparison)
	host.button(row,'展开 / 收起正面对比',func():comparison.visible=not comparison.visible)
	host.label(comparison,'左：正面基准　　右：当前动作（同一显示画布，已应用旧素材缩小）')
	var background_row=HBoxContainer.new();comparison.add_child(background_row)
	var background_label=host.label(background_row,'检查背景');background_label.autowrap_mode=TextServer.AUTOWRAP_OFF
	var backgrounds=OptionButton.new();background_row.add_child(backgrounds)
	for name in ['纯黑 · 白边检查','纯白 · 暗边检查','暖米白']:backgrounds.add_item(name)
	backgrounds.item_selected.connect(func(i):set_inspection_background([Color.BLACK,Color.WHITE,Color('#f3ece1')][i]))
	var previews=HBoxContainer.new();comparison.add_child(previews)
	for i in range(2):
		var panel=PanelContainer.new();panel.custom_minimum_size=Vector2(240,240);previews.add_child(panel);preview_panels.append(panel)
		var view=TextureRect.new();view.custom_minimum_size=Vector2(240,240)
		view.expand_mode=TextureRect.EXPAND_IGNORE_SIZE;view.stretch_mode=TextureRect.STRETCH_KEEP_ASPECT_CENTERED;panel.add_child(view)
		var canvas=GradientTexture2D.new();canvas.width=528;canvas.height=320;view.texture=canvas
		var preview_material=ShaderMaterial.new();preview_material.shader=preload('res://src/preview.gdshader');view.material=preview_material
		if i==0:reference_preview=view
		else:motion_preview=view
	host.label(col,'当前片段进度（拖动可逐帧检查）')
	scrub=HSlider.new();scrub.step=1;col.add_child(scrub)
	scrub.value_changed.connect(func(value):
		if not updating and state!=null:
			paused=true;pause_button.text='继续';state.frame=int(value);state.elapsed=0;host.blend_time=1)
	info=host.label(col,'')
	host.label(col,'连续测试：进入 → 循环保持 → 收尾 → 站立 → 下一个动作。看书用“结束当前动作”退出；睡觉和赌气也可点击桌宠唤醒。')
	close_requested.connect(leave)
	set_inspection_background(Color.BLACK)
	hide()
func set_inspection_background(color: Color):
	inspection_background=color
	for panel in preview_panels:
		var style=StyleBoxFlat.new();style.bg_color=color;panel.add_theme_stylebox_override('panel',style)
	if is_instance_valid(desktop_backdrop):desktop_backdrop.color=color
func open():
	if not active:
		state=State.new(host.manifest);state.looked=true;state.rested=true;state.blink_seconds=-1e9;state.next_wave=1e9;active=true;paused=false;max_delta=0
	show();grab_focus()
func leave():
	active=false;automatic=false;pending_action='';hide();host.blend_time=1
	if is_instance_valid(desktop_backdrop):desktop_backdrop.hide()
func choose(action: String):
	open();automatic=false;selected=action;pending_action=action;paused=false;pause_button.text='暂停';release_current()
func release_current():
	state.busy=false;state.reading=false;state.agent_mode='';state.pending_feedback='';state.pinch_dragging=false;state.released=true
func start_action(action: String):
	selected=action;state.released=false;state.elapsed=0;held_time=0;idle_time=0
	if action in State.FEEDBACK:
		state._start_feedback(action);return
	match action:
		'read':state.set_reading(true)
		'task':state.set_busy(true)
		'sleep','sleep_alt':state.rest_prefix=action;state._switch(action+'_enter')
		'sulk':state._switch('sulk_enter')
		_:state._switch(action)
func start_sequence():
	open();automatic=true;paused=false;pause_button.text='暂停';sequence_index=1;pending_action=str(ACTIONS[sequence_index][1]);release_current()
func if_ready_step():
	if host.frames.ready(str(host.frames.groups[state.frame])):state.advance(1.0/24.0)
func update(delta: float):
	if not active:return
	max_delta=max(max_delta,delta)
	update_preview(reference_preview,int(host.manifest.idle[0]))
	update_preview(motion_preview,host.display_frame)
	# Keep autonomous timers disabled in the isolated test state.
	state.looked=true;state.rested=true;state.blink_seconds=-1e9;state.next_wave=1e9;state.sulk_at=-1
	if not paused and not host.loading:
		if state.phase.ends_with('_loop') or state.phase in ['work','sulk_hold','candy_hold','candy_close_hold','pinch_hold']:
			held_time+=delta*speed
			if automatic and held_time>=3:release_current()
	settle()
	updating=true;scrub.min_value=state.clips[state.phase][0];scrub.max_value=state.clips[state.phase][1];scrub.value=state.frame;updating=false
	info.text='动作：%s  ·  片段：%s\n帧：%d / %d  ·  循环：%d  ·  %s\n渲染：%d FPS  ·  本次最长帧：%.1f ms'%[action_title(selected),phase_title(state.phase),state.frame-int(scrub.min_value)+1,int(scrub.max_value-scrub.min_value)+1,state.loops,'连续测试中' if automatic else ('已暂停' if paused else '播放中'),Engine.get_frames_per_second(),max_delta*1000]

func preload_action() -> String:
	var action=pending_action
	if action.is_empty() and automatic and sequence_index+1<ACTIONS.size():action=str(ACTIONS[sequence_index+1][1])
	if action.is_empty():return ''
	var phase={'read':'read_enter','task':'enter','sulk':'sulk_enter','sleep':'sleep_enter','sleep_alt':'sleep_alt_enter','pinch':'pinch_enter','candy':'candy_enter','candy_close':'candy_close_enter','thinking':'thinking_enter','blocked':'blocked_enter'}.get(action,action)
	return str(host.frames.groups[int(host.manifest[phase][0])])

func action_title(action: String) -> String:
	for item in ACTIONS:
		if item[1]==action:return str(item[0])
	return action
func phase_title(phase: String) -> String:
	if phase in ['enter','work','exit']:return {'enter':'准备工作','work':'工作循环','exit':'收好电脑'}[phase]
	for suffix in ['_enter','_loop','_hold','_exit']:
		if phase.ends_with(suffix):return action_title(phase.trim_suffix(suffix))+' · '+{'_enter':'进入','_loop':'保持','_hold':'保持','_exit':'收尾'}[suffix]
	return action_title(phase)

# Resolve queued actions before rendering, so a one-frame idle pose never flashes between them.
func settle() -> bool:
	if not active or paused:return true
	if state.finished:
		state.finished=false;state.quitting=false;state._switch('idle')
	if state.phase!='idle':return true
	if pending_action.is_empty() and automatic:
		sequence_index+=1
		if sequence_index>=ACTIONS.size():automatic=false
		else:pending_action=str(ACTIONS[sequence_index][1])
	if pending_action.is_empty():return true
	var group=preload_action()
	if not host.frames.ready(group):return false
	var action=pending_action;pending_action='';start_action(action)
	return true

func update_preview(view: TextureRect, index: int):
	var mat=view.material as ShaderMaterial
	var texture=host.frames.textures.get(index)
	mat.set_shader_parameter('loaded',texture!=null)
	if texture!=null:mat.set_shader_parameter('source_texture',texture)
	mat.set_shader_parameter('sprite_rect',host.frames.texture_rect(index))

func resolve_feedback():
	if state.phase.begins_with('blocked'):
		state.agent_mode='';state.feedback('resolved')
	elif state.phase.begins_with('thinking'):
		state.agent_mode='';state.feedback('thinking_done')
	else:state.interact()
