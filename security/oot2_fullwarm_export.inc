// Included only by the offline descriptor tool, after nvn_mtl.m. There is no
// compiler, pipeline-state creation, command submission or fake successful PSO.
// All descriptors come from the real warm_parse/pso_desc/mtk_desc4 paths.
#include "oot2_fullwarm_enums.h"
static NSMutableArray *full_libraries, *full_functions, *full_specialized, *full_render, *full_mesh;
static NSMutableDictionary *full_library_names;
static NSString *full_directory;
static unsigned full_period, full_rows, full_failed, full_rrows, full_mrows;
static unsigned full_emitted_r, full_emitted_m, full_device_r;

static void full_reset(void) {
    full_libraries = [NSMutableArray array]; full_functions = [NSMutableArray array]; full_specialized = [NSMutableArray array];
    full_render = [NSMutableArray array]; full_mesh = [NSMutableArray array]; full_library_names = [NSMutableDictionary dictionary];
}
static void full_flush(void) {
    if (!full_render.count && !full_mesh.count) return;
    NSDictionary *script = @{@"libraries": full_libraries,
        @"function_descriptors": @{@"library_function_descriptors": full_functions, @"specialized_function_descriptors": full_specialized},
        @"pipeline_descriptors": @{@"render_pipeline_descriptors": full_render, @"mesh_render_pipeline_descriptors": full_mesh}};
    NSError *e = nil; NSData *data = [NSJSONSerialization dataWithJSONObject:script options:NSJSONWritingSortedKeys error:&e];
    NSString *path = [full_directory stringByAppendingPathComponent:[NSString stringWithFormat:@"prewarm-%05u.mtl4-json", full_period++]];
    if (!data || ![data writeToFile:path atomically:YES]) { fprintf(stderr, "Full prewarm script write failed\n"); abort(); }
    full_reset();
}
static NSString *full_function(MTL4FunctionDescriptor *descriptor) {
    if (!descriptor) return nil;
    if ([descriptor isKindOfClass:MTL4SpecializedFunctionDescriptor.class]) {
        MTL4SpecializedFunctionDescriptor *special = (id)descriptor;
        NSString *base = full_function(special.functionDescriptor); if (!base) return nil;
        NSDictionary *recorded = full_cv_values(special);
        if (!recorded && special.constantValues) { fprintf(stderr, "Untracked function constants\n"); return nil; }
        NSArray *indices = [[recorded allKeys] sortedArrayUsingSelector:@selector(compare:)];
        NSMutableArray *values = [NSMutableArray array]; for (NSNumber *index in indices) [values addObject:recorded[index]];
        NSString *label = [NSString stringWithFormat:@"s%lu", (unsigned long)full_specialized.count];
        [full_specialized addObject:@{@"label": label, @"function_descriptor": base, @"constant_values": values}];
        return [@"fnd:" stringByAppendingString:label];
    }
    if (![descriptor isKindOfClass:MTL4LibraryFunctionDescriptor.class]) return nil;
    MTL4LibraryFunctionDescriptor *fn = (id)descriptor;
    NSString *path = fn.library ? objc_getAssociatedObject(fn.library, &g_lib_tag) : nil;
    if (!path || !fn.name || [path hasPrefix:@"/"] || [path containsString:@".."] || [path containsString:@"\\"]) return nil;
    NSString *library = full_library_names[path];
    if (!library) {
        library = [NSString stringWithFormat:@"l%lu", (unsigned long)full_libraries.count]; full_library_names[path] = library;
        [full_libraries addObject:@{@"label": library, @"path": path}];
    }
    NSString *label = [NSString stringWithFormat:@"f%lu", (unsigned long)full_functions.count];
    [full_functions addObject:@{@"label": label, @"library": [@"lib:" stringByAppendingString:library], @"name": fn.name}];
    return [@"fnd:" stringByAppendingString:label];
}
static NSString *full_mask(MTLColorWriteMask mask) {
    if (mask == MTLColorWriteMaskUnspecialized) return @"Unspecialized";
    if (mask == MTLColorWriteMaskAll) return @"All";
    if (!mask) return @"None";
    NSMutableArray *names = [NSMutableArray array];
    if (mask & MTLColorWriteMaskRed) [names addObject:@"Red"];
    if (mask & MTLColorWriteMaskGreen) [names addObject:@"Green"];
    if (mask & MTLColorWriteMaskBlue) [names addObject:@"Blue"];
    if (mask & MTLColorWriteMaskAlpha) [names addObject:@"Alpha"];
    return [names componentsJoinedByString:@" "];
}
static NSArray *full_colors(MTL4RenderPipelineColorAttachmentDescriptorArray *attachments) {
    NSMutableArray *out = [NSMutableArray array];
    for (NSUInteger i = 0; i < 8; i++) {
        MTL4RenderPipelineColorAttachmentDescriptor *a = attachments[i];
        [out addObject:@{@"pixel_format": full_enum("MTLPixelFormat", a.pixelFormat), @"write_mask": full_mask(a.writeMask),
            @"blending_state": full_enum("MTL4BlendState", a.blendingState),
            @"source_rgb_blend_factor": full_enum("MTLBlendFactor", a.sourceRGBBlendFactor),
            @"destination_rgb_blend_factor": full_enum("MTLBlendFactor", a.destinationRGBBlendFactor),
            @"source_alpha_blend_factor": full_enum("MTLBlendFactor", a.sourceAlphaBlendFactor),
            @"destination_alpha_blend_factor": full_enum("MTLBlendFactor", a.destinationAlphaBlendFactor),
            @"rgb_blend_operation": full_enum("MTLBlendOperation", a.rgbBlendOperation),
            @"alpha_blend_operation": full_enum("MTLBlendOperation", a.alphaBlendOperation)}];
    }
    return out;
}
static NSDictionary *full_vertex(MTLVertexDescriptor *descriptor) {
    NSMutableArray *attributes = [NSMutableArray array], *layouts = [NSMutableArray array];
    for (NSUInteger i = 0; i < 31; i++) {
        MTLVertexAttributeDescriptor *a = descriptor.attributes[i]; MTLVertexBufferLayoutDescriptor *l = descriptor.layouts[i];
        [attributes addObject:@{@"format": full_enum("MTLVertexFormat", a.format), @"offset": @(a.offset), @"buffer_index": @(a.bufferIndex)}];
        [layouts addObject:@{@"stride": @(l.stride), @"step_function": full_enum("MTLVertexStepFunction", l.stepFunction), @"step_rate": @(l.stepRate)}];
    }
    return @{@"attributes": attributes, @"layouts": layouts};
}
static int full_add_render(MTL4RenderPipelineDescriptor *d) {
    if (!d) return 0;
    NSString *vf = full_function(d.vertexFunctionDescriptor), *ff = full_function(d.fragmentFunctionDescriptor);
    if (!vf || (d.fragmentFunctionDescriptor && !ff)) return 0;
    NSMutableDictionary *row = [@{@"vertex_function_descriptor": vf, @"raster_sample_count": @(d.rasterSampleCount),
        @"alpha_to_coverage_state": full_enum("MTL4AlphaToCoverageState", d.alphaToCoverageState),
        @"rasterization_enabled": @(d.rasterizationEnabled), @"input_primitive_topology": full_enum("MTLPrimitiveTopologyClass", d.inputPrimitiveTopology),
        @"max_vertex_amplification_count": @(d.maxVertexAmplificationCount), @"color_attachments": full_colors(d.colorAttachments)} mutableCopy];
    if (ff) row[@"fragment_function_descriptor"] = ff;
    if (d.vertexDescriptor) row[@"vertex_descriptor"] = full_vertex(d.vertexDescriptor);
    [full_render addObject:row]; full_emitted_r++; return 1;
}
static int full_add_mesh(MTL4MeshRenderPipelineDescriptor *d) {
    if (!d) return 0;
    NSString *of = full_function(d.objectFunctionDescriptor), *mf = full_function(d.meshFunctionDescriptor), *ff = full_function(d.fragmentFunctionDescriptor);
    if (!of || !mf || !ff) return 0;
    [full_mesh addObject:@{@"object_function_descriptor": of, @"mesh_function_descriptor": mf, @"fragment_function_descriptor": ff,
        @"max_total_threads_per_object_threadgroup": @(d.maxTotalThreadsPerObjectThreadgroup),
        @"max_total_threads_per_mesh_threadgroup": @(d.maxTotalThreadsPerMeshThreadgroup), @"payload_memory_length": @(d.payloadMemoryLength),
        @"raster_sample_count": @(d.rasterSampleCount), @"alpha_to_coverage_state": full_enum("MTL4AlphaToCoverageState", d.alphaToCoverageState),
        @"color_attachments": full_colors(d.colorAttachments)}];
    full_emitted_m++; return 1;
}
// Same load and descriptor construction as warm_task, but no pipeline creation.
// In particular, a mesh's task payload and no-task object function are native.
static int full_task(WarmTask *task) {
    pso_skey sk; [task->rs[0] getBytes:&sk length:sizeof sk];
    NvShader *vs = warm_shader(task->vkey, sk.vs_stage), *fs = task->fkey.length ? warm_shader(task->fkey, sk.fs_stage) : nil;
    if (!vs || (task->fkey.length && !fs)) return 0;
    if (task->kind == 3) {
        NvShader *ts = task->tkey ? warm_shader(task->tkey, 3) : nil;
        if (vs->stage != 4 || vs->mesh_kind != 2 || !vs->fn ||
            (fs && (fs->stage != 1 || !fs->fn)) ||
            (task->tkey ? (!ts || ts->stage != 3 || ts->mesh_kind != 1 || !ts->fn || vs->mesh_notask) : !vs->mesh_notask)) return 0;
        MTLRenderPipelineDescriptor *r = pso_desc(&sk.k, nil, fs, nil, 0);
        id<MTLFunction> ff = r.fragmentFunction;
        if (!ff) return 0; // No invented library for an embedded fallback function.
        return full_add_mesh(mtk_desc4(r, ts, vs, ff, sk.k.border));
    }
    int ok = 1;
    for (NSData *row in task->rs) {
        [row getBytes:&sk length:sizeof sk]; id<MTLFunction> fsfn = nil;
        if (sk.fz) {
            if (sk.fz_desc.kind == 1 && fs) {
                int fx[32]; for (int i = 0; i < 32; i++) fx[i] = sk.fz_desc.fx[i];
                fsfn = bf_fn(fs, fx, sk.fz_desc.fbmask, sk.k.lmap);
            }
            if (!fsfn) { ok = 0; continue; }
        }
        pso_key key = sk.k; key.vs = (__bridge void *)vs; key.fs = (__bridge void *)fs; key.fsfn = (__bridge void *)fsfn;
        MTLRenderPipelineDescriptor *r = pso_desc(&key, vs, fs, fsfn, sk.merged);
        // pso_desc4 deliberately returns nil for rasterized depth-only rows:
        // Metal 4 requires a fragment, while the runtime uses MTLDevice here.
        // Keep those exact recorded rows in native device prewarm; never invent
        // a fragment, disable rasterization, or silently omit their coverage.
        if (!fs && !sk.fz && r.rasterizationEnabled && !r.fragmentFunction) {
            full_device_r++; continue;
        }
        int unspecialized = r.rasterizationEnabled && ![r.label isEqualToString:PSO_WHOLE];
        if (!full_add_render(pso_desc4(r, unspecialized, !key.border))) ok = 0;
        if (full_render.count + full_mesh.count >= 256) full_flush();
    }
    return ok;
}
static int full_export_lists(NSString *manifest, NSString *directory) {
    full_directory = directory; full_reset();
    [NSFileManager.defaultManager createDirectoryAtPath:directory withIntermediateDirectories:YES attributes:nil error:nil];
    // warm_parse deliberately skips invalid rows for gameplay. Offline builds
    // must account for them explicitly before claiming complete list coverage.
    NSMutableSet *input_seen = [NSMutableSet set], *render_seen = [NSMutableSet set];
    unsigned expected_r = 0, expected_m = 0, invalid = 0;
    NSString *text = [NSString stringWithContentsOfFile:manifest encoding:NSUTF8StringEncoding error:nil];
    if (!text) return 1;
    for (NSString *line in [text componentsSeparatedByString:@"\n"]) {
        if ([input_seen containsObject:line]) continue;
        [input_seen addObject:line]; NSArray *c = [line componentsSeparatedByString:@"\t"];
        if ([c[0] isEqualToString:@"R"]) {
            pso_skey sk;
            if (c.count != 2 || pso_skey_parse([c[1] UTF8String], &sk)) { invalid++; continue; }
            NSData *key = [NSData dataWithBytes:&sk length:sizeof sk];
            if (![render_seen containsObject:key]) { [render_seen addObject:key]; expected_r++; }
        } else if ([c[0] isEqualToString:@"M"]) {
            pso_skey sk;
            if (c.count != 3 || pso_mesh_skey_parse([c[2] UTF8String], &sk)) { invalid++; continue; }
            expected_m++;
        }
    }
    if (invalid) { fprintf(stderr, "Invalid recorded R/M rows: %u\n", invalid); return 1; }
    shmap_load(); warm_load_begin(); long lines = 0;
    NSArray<WarmTask *> *tasks = warm_parse(@[manifest], &lines);
    for (WarmTask *task in tasks) {
        if (task->kind != 1 && task->kind != 3) continue;
        unsigned rows = task->kind == 1 ? (unsigned)task->rs.count : 1;
        full_rows += rows; if (task->kind == 1) full_rrows += rows; else full_mrows += rows;
        if (!full_task(task)) full_failed++;
        if (full_render.count + full_mesh.count >= 256) full_flush();
    }
    full_flush();
    if (expected_r != full_rrows || expected_m != full_mrows) full_failed++;
    NSDictionary *coverage = @{@"chain": @(DMSH_CHAIN), @"render_rows": @(full_rrows), @"mesh_rows": @(full_mrows),
        @"rows": @(full_rows), @"failed_tasks": @(full_failed), @"periods": @(full_period), @"stale_keys": @(g_warm_skip_stale),
        @"emitted_render": @(full_emitted_r), @"device_render_rows": @(full_device_r),
        @"device_render_reason": @"metal4_requires_fragment", @"emitted_mesh": @(full_emitted_m),
        @"pipeline_creation_used": @NO, @"new_shaders_compiled": @NO};
    NSData *report = [NSJSONSerialization dataWithJSONObject:coverage options:NSJSONWritingSortedKeys error:nil];
    [report writeToFile:[directory stringByAppendingPathComponent:@"coverage.json"] atomically:YES];
    printf("Full prewarm descriptors: R=%u M=%u device-depth=%u failed=%u periods=%u\n", full_rrows, full_mrows, full_device_r, full_failed, full_period);
    return full_failed || !full_rrows || !full_mrows || full_emitted_r + full_device_r != full_rrows || full_emitted_m != full_mrows;
}
