extends SceneTree
var pet
func _initialize():call_deferred('run')
func require(value: bool,message: String):
	if not value:printerr('UI_FLOW_FAIL ',message);quit(1)
func run():
	pet=load('res://main.tscn').instantiate();root.add_child(pet)
	await create_timer(.2).timeout
	require(not pet.alert.visible,'no empty reminder window at startup')
	require(not pet.panel.visible,'panel starts hidden')
	pet.prompt.text='1秒后提醒我自动测试'
	await pet.submit()
	require(pet.result.text.contains('提醒') or pet.result.text.contains('记好了'),'reminder saved response')
	await create_timer(1.5).timeout
	if pet.polling:await create_timer(1).timeout
	await pet.poll()
	require(pet.alert.visible and not pet.shown_due.is_empty(),'due alert visible')
	await pet.dismiss_due();require(not pet.alert.visible,'due alert dismissed')
	pet.animation.advance(10)
	pet.toggle_reading();pet.animation.advance(4)
	require(pet.animation.phase=='read_loop','reading loop entered')
	pet.animation.interact();pet.animation.advance(2)
	require(pet.animation.phase=='read_loop','reading survives click')
	pet.toggle_reading();pet.animation.advance(5)
	require(pet.animation.phase=='idle','exit reading finishes')
	pet.begin_quit();pet.animation.advance(3)
	require(pet.animation.finished,'goodbye plays before exit')
	print('UI_FLOW_PASS reminder save/due/dismiss, read/click/exit, goodbye')
	quit()
