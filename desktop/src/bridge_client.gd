class_name LuluBridgeClient
extends Node
var port := 8766
var token := ""
var connected := false

func request_api(method: HTTPClient.Method, path: String, payload: Dictionary = {}) -> Dictionary:
	var connection_path := OS.get_environment('LULU_CONNECTION')
	if connection_path.is_empty(): connection_path = ProjectSettings.globalize_path('res://../data/connection.json')
	var connection = JSON.parse_string(FileAccess.get_file_as_string(connection_path)) if FileAccess.file_exists(connection_path) else null
	if not connection is Dictionary:
		connected = false
		return {'error':'正在等待本机服务启动…'}
	port = int(connection.port); token = str(connection.token)
	var request := HTTPRequest.new()
	request.timeout = 8.0; request.body_size_limit = 8000000
	add_child(request)
	var headers := PackedStringArray(['Content-Type: application/json', 'X-Lulu-Token: ' + token])
	var error := request.request('http://127.0.0.1:%s/api/%s' % [port,path], headers, method, JSON.stringify(payload) if method != HTTPClient.METHOD_GET else '')
	if error != OK:
		request.queue_free(); connected=false
		return {'error':'连接暂时不可用，正在重连…'}
	var response: Array = await request.request_completed
	request.queue_free()
	connected = response[0] == HTTPRequest.RESULT_SUCCESS and int(response[1]) != 403
	if not connected: return {'error':'本机服务连接中断，正在重连…'}
	var parsed = JSON.parse_string((response[3] as PackedByteArray).get_string_from_utf8())
	if parsed is Array: return {'items':parsed}
	if not parsed is Dictionary: return {'error':'服务未返回有效数据'}
	if int(response[1]) >= 400 and not parsed.has('error'): parsed['error']='操作未完成，请重试。'
	return parsed
