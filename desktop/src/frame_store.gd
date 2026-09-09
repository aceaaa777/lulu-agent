extends RefCounted
# Decode off the render path; retain complete banks so held loops never thrash.
var manifest: Dictionary
var textures: Dictionary = {}
var paths: Dictionary = {}
var groups: Dictionary = {}
var queue: Array[int] = []
var pending: Dictionary = {}
var recent: Array[String] = []
var pinned: Array = []
var optimized: Dictionary = {}
var members: Dictionary = {}
var loaded_counts: Dictionary = {}
var cached_bytes: int = 0
var disabled: bool = false  # no frame files at all (exported build without frames.pck): stay quiet instead of erroring per frame
const CACHE_BUDGET = 192 * 1024 * 1024
func _init(data: Dictionary):
	manifest=data
	for i in range(362):
		paths[i]='res://assets/frames/frame_%04d.png'%i;groups[i]='base'
	for bank in data.banks:
		for j in range(int(bank.count)):
			var i=int(bank.start)+j
			paths[i]='res://assets/scenes/%s/%04d.png'%[bank.code,j];groups[i]=str(bank.code)
	if FileAccess.file_exists('res://assets/optimized.json'):
		optimized=JSON.parse_string(FileAccess.get_file_as_string('res://assets/optimized.json'))
	for i in paths:
		if optimized.has(str(i)):paths[i]=optimized[str(i)].path
		var group=str(groups[i])
		if not members.has(group):members[group]=[];loaded_counts[group]=0
		members[group].append(i)
	if not ResourceLoader.exists(paths[int(data.idle[0])]):
		disabled=true;push_warning('animation frames unavailable: '+paths[int(data.idle[0])]);return
	for i in range(int(data.idle[0]),int(data.idle[1])+1):_put(i,load(paths[i]))
	ensure('base')
func ensure(group: String):
	if disabled:return
	if group in recent: recent.erase(group)
	recent.append(group)
	for i in members.get(group,[]):
		if not textures.has(i) and not pending.has(i) and not i in queue:queue.append(i)
	trim()
func _put(index: int, tex: Texture2D):
	if tex==null:return
	if textures.has(index):return
	textures[index]=tex
	loaded_counts[groups[index]]+=1
	cached_bytes+=tex.get_width()*tex.get_height()*4
func trim():
	# Complete active/transition banks stay pinned; evict only older, reusable banks.
	var scenes=recent.filter(func(g):return g!='base')
	while scenes.size()>2 or (cached_bytes>CACHE_BUDGET and scenes.size()>1):
		var candidates=scenes.filter(func(g):return not g in pinned and g!=recent.back())
		if candidates.is_empty():break
		var old=candidates[0];scenes.erase(old);recent.erase(old)
		for i in members[old]:
			if textures.has(i):
				var tex=textures[i];cached_bytes-=tex.get_width()*tex.get_height()*4
				textures.erase(i);loaded_counts[old]-=1
		queue=queue.filter(func(i):return groups[i]!=old)
func ready(group: String) -> bool:
	return members.has(group) and loaded_counts[group]==members[group].size()
func pump():
	if disabled:return
	var started=Time.get_ticks_usec()
	for i in pending.keys():
		var status=ResourceLoader.load_threaded_get_status(paths[i])
		if status==ResourceLoader.THREAD_LOAD_LOADED:
			var tex=ResourceLoader.load_threaded_get(paths[i]);pending.erase(i)
			if groups[i] in recent:_put(i,tex)
		elif status==ResourceLoader.THREAD_LOAD_FAILED:
			push_error('Animation frame could not load: '+paths[i]);pending.erase(i)
		if Time.get_ticks_usec()-started>2000:break
	while pending.size()<8 and not queue.is_empty():
		var i=queue.pop_front()
		if textures.has(i):continue
		if ResourceLoader.load_threaded_request(paths[i],'Texture2D',false,ResourceLoader.CACHE_MODE_IGNORE)==OK:pending[i]=true
	trim()
func rect(index: int) -> Rect2:
	var group=str(groups.get(index,'base'))
	var framing=manifest.get('framing',{}).get(group,{})
	var scale=float(framing.get('scale',1));var floor_y=float(framing.get('floor',336));var center=float(framing.get('center',192))
	if framing.has('track'):
		for bank in manifest.banks:
			if str(bank.code)==group:
				var point=framing.track[index-int(bank.start)];scale=point[0];floor_y=point[1];center=point[2];break
	var ratio=320.0/384.0
	return Rect2(Vector2(192-center*scale,336-floor_y*scale)*ratio,Vector2.ONE*320*scale)

func display_rect(index: int) -> Vector4:
	var calibration=manifest.get('display_calibration',{}).get(str(groups.get(index,'base')),{})
	if calibration.has('rect'):
		var r=calibration.rect
		return Vector4(r[0],r[1],r[2],r[3])
	if str(groups.get(index,'base')) in manifest.get('native_banks',[]):return Vector4(0,20,528,297)
	var scale=float(manifest.get('legacy_display_scale',1.0))
	return Vector4(264-160*scale,280-280*scale,320*scale,320*scale)

# Preserve the original logical rectangle for all calibration and animation logic.
# Only the uploaded texture rectangle loses transparent margins.
func texture_rect(index: int) -> Vector4:
	var r=display_rect(index)
	if not optimized.has(str(index)):return r
	var c=optimized[str(index)].crop
	return Vector4(r.x+r.z*c[0]/c[4],r.y+r.w*c[1]/c[5],r.z*c[2]/c[4],r.w*c[3]/c[5])
