extends SceneTree
var failures=0
var checks=0
func check(ok: bool,message: String):
 checks+=1
 if not ok:failures+=1;printerr('LEGACY_SCALE_FAIL ',message)
func _initialize():call_deferred('run')
func run():
 var pet=load('res://main.tscn').instantiate();root.add_child(pet);pet.set_process(false);pet.polling=true;pet.lab.open()
 var reference=int(pet.manifest.idle[0]);var targets=[['reference',reference],['cloudy',pet.manifest.cloudy[0]+60],['read',pet.manifest.read_enter[0]],['read_alt',pet.manifest.read_alt[0]],['work',120],['wave',265],['sulk',325]]
 for item in targets:
  var frame=int(item[1]);var group=str(pet.frames.groups[frame]);pet.frames.pinned=[group,str(pet.frames.groups[reference])];pet.frames.ensure(group)
  while not pet.frames.ready(group):pet.frames.pump();await process_frame
  var r=pet.frames.display_rect(frame)
  if group in pet.manifest.native_banks:check(r==Vector4(0,20,528,297),'new material transform unchanged')
  else:
   check(is_equal_approx(r.z,294.4) and is_equal_approx(r.w,294.4),'old material uses one 92 percent scale '+item[0])
   check(is_equal_approx(r.x+r.z*.5,264) and is_equal_approx(r.y+r.w*280/320,280),'center and foot anchor stable '+item[0])
  pet.display_frame=frame;pet.blend_from=reference
  for progress in [0.0,.5,1.0]:
   pet.blend_time=progress*.16;pet.queue_redraw();pet.lab.update(0)
   await process_frame;await RenderingServer.frame_post_draw
   check(root.get_texture().get_image().get_pixel(264,200).a>.98,'body opacity during transition '+item[0]+' '+str(progress))
  root.get_texture().get_image().save_png('res://.local/legacy-'+item[0]+'.png')
  if item[0]=='read':pet.lab.get_texture().get_image().save_png('res://.local/legacy-panel.png')
 print('LEGACY_SCALE ',checks,' checks, ',failures,' failures');quit(1 if failures else 0)
