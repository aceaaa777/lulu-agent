extends SceneTree
func _initialize():call_deferred('run')
func run():
	var pet=load('res://main.tscn').instantiate();root.add_child(pet);pet.polling=true;pet.lab.open()
	await create_timer(2).timeout
	await RenderingServer.frame_post_draw
	pet.lab.get_texture().get_image().save_png('res://.local/animation-panel.png')
	print('PANEL_SNAPSHOT_PASS');quit()
