extends SceneTree
func _initialize():call_deferred('run')
func run():
	var tag='before'
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with('--snapshot='):tag=arg.trim_prefix('--snapshot=')
	var pet=load('res://main.tscn').instantiate();root.add_child(pet);pet.set_process(false);pet.polling=true;pet.refreshing=true;pet.panel.hide();pet.pet_chrome.hide()
	var report=[]
	var banks=[{'code':'base','start':0,'count':362}]+pet.manifest.banks
	for bank in banks:
		var group=str(bank.code);pet.frames.pinned=[];var began=Time.get_ticks_msec();pet.frames.ensure(group)
		while not pet.frames.ready(group):
			pet.frames.pump();await process_frame
			if Time.get_ticks_msec()-began>60000:printerr('LOAD_TIMEOUT ',group);quit(1);return
		var bytes=0
		for tex in pet.frames.textures.values():bytes+=tex.get_width()*tex.get_height()*4
		report.append({'bank':group,'load_ms':Time.get_ticks_msec()-began,'cached_frames':pet.frames.textures.size(),'texture_bytes':bytes})
		for offset in [0,int(bank.count)/2,int(bank.count)-1]:
			pet.display_frame=int(bank.start)+int(offset);pet.blend_from=pet.display_frame;pet.blend_time=1;pet.queue_redraw()
			await process_frame;await RenderingServer.frame_post_draw
			root.get_texture().get_image().save_png('res://../validation/animation-optimization/'+tag+'/'+str(pet.display_frame)+'.png')
	var f=FileAccess.open('res://../validation/animation-optimization/'+tag+'/metrics.json',FileAccess.WRITE);f.store_string(JSON.stringify(report));f.close()
	print('RESOURCE_BENCHMARK ',tag,' banks=',banks.size());quit()
