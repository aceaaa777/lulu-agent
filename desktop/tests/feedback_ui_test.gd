extends SceneTree
class MockBridge extends Node:
	var task_status='queued'
	var reject=false
	var care=null
	func request_api(_method,path,_payload={}) -> Dictionary:
		if path=='/api/assistant':
			if reject:return {'error':'请补充目标'}
			return {'task':{'id':'test'}}
		if path=='/api/tasks':return {'tasks':[{'id':'test','status':task_status,'result':'完成','error':'无法完成'}]}
		if path=='/api/companion':return {'care':{'event':care}}
		return {'ok':true}
var failures=0
var checks=0
func check(ok: bool,msg: String):
	checks+=1
	if not ok:failures+=1;printerr('FEEDBACK_UI_FAIL ',msg)
func _initialize():call_deferred('run')
func run():
	var pet=load('res://main.tscn').instantiate();root.add_child(pet);pet.set_process(false);pet.polling=true
	pet.bridge.queue_free();var mock=MockBridge.new();pet.add_child(mock);pet.bridge=mock
	pet.prompt.text='测试任务';await pet.submit()
	check(pet.animation.agent_mode=='thinking','submit starts thinking')
	mock.task_status='completed';await pet.poll();pet.animation.advance(15)
	check(pet.animation.history.any(func(h):return h.phase=='thinking_done'),'real completion insight')
	check(pet.animation.history.any(func(h):return h.phase=='complete'),'real completion sign')
	pet.animation=load('res://src/animation_state.gd').new(pet.manifest)
	mock.reject=true;await pet.submit();pet.animation.advance(6)
	check(pet.animation.phase=='blocked_loop','rejected target stays blocked')
	mock.reject=false;mock.task_status='queued';await pet.submit()
	check(pet.animation.recovered,'resubmission remembers blocked context')
	mock.task_status='completed';await pet.poll();pet.animation.advance(18)
	check(pet.animation.history.any(func(h):return h.phase=='resolved'),'successful resubmission resolves')
	pet.animation=load('res://src/animation_state.gd').new(pet.manifest);mock.task_status='queued';await pet.submit()
	mock.task_status='failed';await pet.poll();pet.animation.advance(8)
	check(pet.animation.phase=='blocked_loop','failed task is not success')
	pet.animation=load('res://src/animation_state.gd').new(pet.manifest);pet.task_id='';pet.task_active=false;mock.care={'id':1,'action':'candy'}
	await pet.poll();pet.animation.advance(8);check(pet.animation.phase=='candy_hold','care event enters offering')
	await pet.poll();check(pet.animation.pending_feedback=='','same care event never replays')
	pet.animation.interact();pet.animation.advance(5);check(pet.animation.phase=='idle','care click finishes')
	print('FEEDBACK_UI ',checks,' checks, ',failures,' failures');quit(1 if failures else 0)
