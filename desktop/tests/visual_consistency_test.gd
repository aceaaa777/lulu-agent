extends SceneTree
var pet
var failures=0
var checks=0
var report=[]
func check(ok,message):
	checks+=1
	if not ok:failures+=1;printerr('CONSISTENCY_FAIL ',message)
func _initialize():call_deferred('run')
func prepare(frame):
	var group=str(pet.frames.groups[frame]);pet.frames.pinned=[group,'2822'];pet.frames.ensure(group)
	while not pet.frames.ready(group):pet.frames.pump();await process_frame
func capture():
	pet.queue_redraw();await process_frame;await RenderingServer.frame_post_draw
	return root.get_texture().get_image()
func bounds(im):
	var left=528;var top=320;var right=0;var bottom=0
	for y in range(320):
		for x in range(528):
			if im.get_pixel(x,y).a>0.94:left=mini(left,x);top=mini(top,y);right=maxi(right,x);bottom=maxi(bottom,y)
	return Rect2i(left,top,right-left+1,bottom-top+1)
func run():
	pet=load('res://main.tscn').instantiate();root.add_child(pet);pet.set_process(false);pet.polling=true;pet.refreshing=true;pet.diagnostic_time=-10000;pet.panel.hide();pet.pet_chrome.hide()
	var base=int(pet.manifest.idle[0]);await prepare(base)
	pet.display_frame=base;pet.blend_from=base;pet.blend_time=1
	var baseline=bounds(await capture())
	for code in pet.manifest.display_calibration:
		var frame=int(pet.manifest.display_calibration[code].reference_frame);await prepare(frame)
		pet.display_frame=frame;pet.blend_from=frame;pet.blend_time=1
		var im=await capture();var b=bounds(im)
		check(absi(b.size.y-baseline.size.y)<=4,'standing height '+code+' '+str(b))
		check(absi(b.end.y-baseline.end.y)<=3,'feet baseline '+code+' '+str(b))
		check(absf(b.get_center().x-baseline.get_center().x)<=3,'body center '+code)
		check(im.get_pixel(10,10).a<0.01,'transparent surroundings '+code)
		report.append({'bank':code,'bounds':str(b)})
		im.save_png('res://../validation/visual-fix/normalized-'+code+'.png')
	# Inspect complete silhouettes throughout the two formerly mismatched transitions.
	for code in ['4321','6157']:
		var frame=int(pet.manifest.display_calibration[code].reference_frame);await prepare(base);await prepare(frame)
		pet.blend_from=base;pet.display_frame=frame
		for step in range(9):
			pet.blend_time=step/8.0*.16
			var im=await capture();var b=bounds(im)
			check(absf(b.size.y-baseline.size.y)<=5,'transition silhouette height '+code+' '+str(step))
			check(im.get_pixel(263,180).a>.99,'body never fades out '+code+' '+str(step))
	check(pet.frames.display_rect(int(pet.manifest.candy_close_enter[0]))==Vector4(0,20,528,297),'explicit close-up keeps original framing')
	# A wrap inside one phase must no longer jump straight to an unmatched first frame.
	await prepare(int(pet.manifest.blocked_loop[0]))
	pet.animation._switch('blocked_loop');pet.animation.agent_mode='blocked';pet.animation.frame=int(pet.manifest.blocked_loop[1]);pet.animation.elapsed=0
	pet.display_frame=pet.animation.frame;pet.last_display_phase='blocked_loop';pet.blend_time=1
	pet._process(1.0/24)
	check(pet.blend_time<.16,'loop seam is eased')
	var first_target=pet.display_frame;var prior=pet.blend_time
	pet.animation._switch('thinking_enter');pet._process(1.0/30)
	check(pet.display_frame==first_target and pet.blend_time>prior,'rapid state change does not restart visible fade')
	# A delayed process callback cannot skip a whole action.
	pet.blend_time=1;pet.animation._switch('pinch_enter');pet.animation.elapsed=0;await prepare(pet.animation.frame)
	pet._process(3.0)
	check(pet.animation.frame<=int(pet.manifest.pinch_enter[0])+4,'stall does not fast-forward through accelerated pinch')
	var f=FileAccess.open('res://../validation/visual-fix/render-bounds.json',FileAccess.WRITE);f.store_string(JSON.stringify(report));f.close()
	print('VISUAL_CONSISTENCY ',checks,' checks, ',failures,' failures');quit(1 if failures else 0)
