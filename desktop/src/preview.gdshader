shader_type canvas_item;
render_mode unshaded;
uniform sampler2D source_texture : filter_linear;
uniform vec4 sprite_rect=vec4(0,20,528,297);
uniform bool loaded=false;
void fragment(){
 vec2 uv=(UV*vec2(528,320)-sprite_rect.xy)/sprite_rect.zw;
 if(!loaded || any(lessThan(uv,vec2(0))) || any(greaterThan(uv,vec2(1)))) COLOR=vec4(0);
 else COLOR=texture(source_texture,uv);
}
