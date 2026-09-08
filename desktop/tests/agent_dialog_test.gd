extends SceneTree
class FakeBridge extends Node:
	func request_api(_method,path,_payload={}):
		if path.begins_with('questions/'):
			return {'task':'continued','session':'session'}
		if path.begins_with('sessions/'):return {'items':[]}
		return {'task':{'goal':'生成今日BTC价格Word','status':'awaiting_input','answer':'需要提供真实数据后继续'},'events':[{'kind':'drafting','detail':'{"path":"行情.docx"}'},{'kind':'harness_tool_failed','detail':'{"tool":"generate_document","error":"缺少可核对的实时数据"}'},{'kind':'user_input_required','detail':'{"question":"请上传行情数据或明确改为模板","reason":"未获取到数据"}'}]}
var failures=0
func check(ok,message):
	if not ok:failures+=1;printerr('DIALOG_FAIL ',message)
func _initialize():call_deferred('run')
func run():
	var pet=load('res://main.tscn').instantiate();root.add_child(pet);pet.set_process(false);pet.polling=true;pet.refreshing=true;pet.prompt.set_block_signals(true)
	pet.bridge.queue_free();pet.bridge=FakeBridge.new();pet.add_child(pet.bridge)
	pet.questions=[{'id':'q1','task':'t1','question':'请提供平台、交易对、时间范围及真实行情数据，或明确改为模板。','reason':'当前未获取到可用实时来源'}]
	pet.open_pending_question();await process_frame;await process_frame
	check(pet.question_window.visible,'question window opened')
	check(pet.question_reply.editable and pet.question_reply.get_global_rect().end.y<pet.question_window.size.y,'answer input accessible')
	await RenderingServer.frame_post_draw;pet.question_window.get_texture().get_image().save_png('res://../validation/agent-input/question.png')
	pet.question_reply.text='先生成一个模板，不填入真实价格。';await pet.answer_pending_question()
	check(pet.task_id=='continued' and pet.animation.recovered,'answer continues with recovery context')
	check(not pet.question_window.visible,'question closes on accepted answer')
	await pet.show_record('t1');await process_frame;await RenderingServer.frame_post_draw
	check(pet.record_window.visible and '缺少可核对' in pet.record_body.text,'execution failure is visible')
	pet.record_window.get_texture().get_image().save_png('res://../validation/agent-input/record.png')
	pet.record_window.hide();pet.panel.size=Vector2i(700,640);await process_frame;await process_frame
	check(pet.run_button.get_global_rect().end.y<640,'composer still fits')
	await RenderingServer.frame_post_draw;pet.panel.get_texture().get_image().save_png('res://../validation/agent-input/panel.png')
	print('AGENT_DIALOG failures=',failures);quit(1 if failures else 0)
