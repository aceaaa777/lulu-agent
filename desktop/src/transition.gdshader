shader_type canvas_item;
render_mode unshaded;
uniform sampler2D previous_texture : filter_linear;
uniform float progress : hint_range(0.0, 1.0) = 1.0;
uniform vec4 next_rect = vec4(0,20,528,297);
uniform vec4 previous_rect = vec4(0,20,528,297);
void fragment() {
 vec2 pixel=UV*vec2(528,320);
 vec2 next_uv=(pixel-next_rect.xy)/next_rect.zw;
 vec2 prev_uv=(pixel-previous_rect.xy)/previous_rect.zw;
 vec4 next=texture(TEXTURE,next_uv);
 vec4 previous=texture(previous_texture,prev_uv);
 if(any(lessThan(next_uv,vec2(0))) || any(greaterThan(next_uv,vec2(1))))next=vec4(0);
 if(any(lessThan(prev_uv,vec2(0))) || any(greaterThan(prev_uv,vec2(1))))previous=vec4(0);
    float t = smoothstep(0.0, 1.0, progress);
    float a = mix(previous.a, next.a, t);
    // One composite: two opaque body pixels stay opaque throughout a transition.
    vec3 premultiplied = mix(previous.rgb * previous.a, next.rgb * next.a, t);
    COLOR = vec4(premultiplied / max(a, 0.00001), a);
}
