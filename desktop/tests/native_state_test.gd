extends SceneTree
const State=preload('res://src/animation_state.gd')
var failures=0
var checks=0
func check(ok: bool,message: String):
 checks+=1
 if not ok:failures+=1;printerr('NATIVE_STATE_FAIL ',message)
func _initialize():
 var m=JSON.parse_string(FileAccess.get_file_as_string('res://assets/clips.json'))
 var s=State.new(m);s.looked=true;s.rested=true;s.next_wave=1e9
 s.advance(9.9);check(s.phase=='idle','no early blink')
 s.advance(.1);check(s.phase=='blink','blink at ten idle seconds')
 s.advance(.625);check(s.phase=='idle','blink returns to idle')
 s.advance(9.375);check(s.history.filter(func(h):return h.phase=='blink').size()==2,'blink repeats after another ten idle seconds')
 s=State.new(m);s.set_reading(true);s.advance(30);check(s.phase=='read_loop','blink never interrupts reading')
 for name in ['sleep','sleep_alt']:
  s=State.new(m);s.preview(name)
  var enter_seconds=(m[name+'_enter'][1]-m[name+'_enter'][0]+1)/24.0
  s.advance(enter_seconds);check(s.phase==name+'_loop','sleep enters loop '+name)
  var loop_seconds=(m[name+'_loop'][1]-m[name+'_loop'][0]+1)/24.0
  s.advance(loop_seconds*3);check(s.phase==name+'_loop' and s.loops==3,'three sleep cycles '+name)
  var before=s.frame;s.interact();check(s.frame==before,'wake does not rewind '+name)
  s.advance(loop_seconds);check(s.phase==name+'_exit','wake starts source exit '+name)
  s.advance(8);check(s.phase=='idle','wake returns to idle '+name)
 for b in m.banks:
  if b.code in m.native_banks:
   var metadata=JSON.parse_string(FileAccess.get_file_as_string('res://assets/optimized.json'))
   var crop=metadata[str(int(b.start))].crop
   check(Vector2i(crop[4],crop[5])==Vector2i(1280,720),'preserved original native dimensions '+b.code)
 print('NATIVE_STATE ',checks,' checks, ',failures,' failures');quit(1 if failures else 0)
