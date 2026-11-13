#include "../nvn/nvn_mtl.m"
void *front_metal_layer(void) { return NULL; }
module_t *module_of(const void *p) { (void)p; return NULL; }
module_t *g_mod; int g_nmod;
void svc_thread_dump(void) {}
uint64_t now_ns(void) { return bp_now(); }

static int fixture_rows(NSString *path) {
    NSMutableString *text = [NSMutableString string];
    NvShader *v = [NvShader new], *f = [NvShader new]; strcpy(v->key, "v_b"); strcpy(f->key, "f_b"); f->stage = 1;
    int fmt = 0; for (int x = 1; x < 256; x++) if (vfmt(x) == MTLVertexFormatFloat4) { fmt = x; break; }
    if (!fmt) return 4;
    for (unsigned offset = 0; offset <= 8; offset += 4) {
        pso_key k = {.samples = 1, .cfmt = {MTLPixelFormatRGBA8Unorm}, .chmask = 15};
        k.attr[0] = (va_st){.fmt = (uint32_t)fmt, .offset = offset}; k.stream[0] = (vs_st){.stride = 32, .divisor = offset == 8 ? 2 : 0};
        pso_skey sk; char hex[sizeof sk * 2 + 1]; pso_skey_from(&k, v, f, 0, NULL, &sk);
        if (offset == 8) { sk.fz = 1; sk.merged = 1; sk.fz_desc.kind = 1; sk.fz_desc.fx[0] = -1; sk.fz_desc.fbmask = 1; }
        pso_skey_hex(&sk, hex);
        [text appendFormat:@"R\t%s\n", hex];
    }
    // Two depth-only variants share one task, just like the real manifest.
    // Rasterization must remain enabled: these update depth through MTLDevice.
    for (unsigned offset = 0; offset <= 4; offset += 4) {
        pso_key k = {.samples = 1, .dfmt = MTLPixelFormatDepth32Float};
        k.attr[0] = (va_st){.fmt = (uint32_t)fmt, .offset = offset};
        k.stream[0] = (vs_st){.stride = 32};
        pso_skey sk; char hex[sizeof sk * 2 + 1]; pso_skey_from(&k, v, nil, 0, NULL, &sk);
        pso_skey_hex(&sk, hex); [text appendFormat:@"R\t%s\n", hex];
    }
    v->stage = 4;
    for (int task = 0; task < 2; task++) {
        strcpy(v->key, task ? "m_b" : "n_b");
        pso_key k = {.samples = 1, .cfmt = {MTLPixelFormatRGBA8Unorm}, .chmask = task ? 15 : 3};
        pso_skey sk; char hex[sizeof sk * 2 + 1]; pso_skey_from(&k, v, f, 0, NULL, &sk); pso_skey_hex(&sk, hex);
        [text appendFormat:@"M\t%s\t%s\n", task ? "t_b" : "-", hex];
    }
    return [text writeToFile:path atomically:YES encoding:NSUTF8StringEncoding error:nil] ? 0 : 5;
}
static int fixture_constants(void) {
    g_full_export = 1; int32_t value = -7; bool yes = true;
    MTLFunctionConstantValues *a = [MTLFunctionConstantValues new];
    full_cv_set(a, &value, MTLDataTypeInt, 1); full_cv_set(a, &yes, MTLDataTypeBool, 2);
    MTL4SpecializedFunctionDescriptor *fd = [MTL4SpecializedFunctionDescriptor new]; full_cv_bind(fd, a);
    MTL4RenderPipelineDescriptor *pipeline = [MTL4RenderPipelineDescriptor new];
    pipeline.vertexFunctionDescriptor = fd;
    MTL4SpecializedFunctionDescriptor *copied = (id)pipeline.vertexFunctionDescriptor;
    NSDictionary *copiedValues = full_cv_values(copied);
    if (copiedValues.count != 2 || [copiedValues[@1][@"value"][@"data"] intValue] != -7) return 8;
    MTLFunctionConstantValues *b = full_cv_copy_from(copied); full_cv_set(b, &yes, MTLDataTypeBool, 3);
    NSDictionary *before = objc_getAssociatedObject(fd, &full_cv_tag), *after = objc_getAssociatedObject(b, &full_cv_tag);
    if (before.count != 2 || after.count != 3 || [before[@1][@"value"][@"data"] intValue] != -7) return 6;
    puts("PASS: typed function constants survive descriptor copy without changing the original."); return 0;
}

int main(int argc, char **argv) { @autoreleasepool {
    if (argc == 3 && !strcmp(argv[1], "--fixture-rows")) return fixture_rows(@(argv[2]));
    if (argc == 2 && !strcmp(argv[1], "--fixture-constants")) return fixture_constants();
    if (argc == 3 && !strcmp(argv[1], "--validate-archive")) return arch_file_ok(@(argv[2])) ? 0 : 7;
    if (argc != 4) return 2;
    // No launch, NSO, RomFS, save mount, pipeline compilation or GPU work.
    setenv("DM_MSL_DIR", argv[1], 1); setenv("DM_NVN_SHMAP", argv[2], 1);
    setenv("DM_PSO_MANIFEST", "off", 1); setenv("DM_PSO_USER", "off", 1);
    setenv("DM_PSO_ARCHIVE", "off", 1); setenv("DM_PSO_BUNDLE", "off", 1);
    setenv("DM_PSO_MTL4", "1", 1); setenv("DM_NVN_PREDICT", "0", 1);
    g_full_export = 1;
    // A real MTLDevice is needed only to expose library/function metadata.
    // Unlike mtl_init(), this creates no queues, GPU buffers or host PSOs.
    g_dev = MTLCreateSystemDefaultDevice();
    if (!g_dev) return 3;
    NSString *manifest = [@(argv[2]).stringByDeletingLastPathComponent stringByAppendingPathComponent:@"pso_manifest.tsv"];
    return full_export_lists(manifest, @(argv[3]));
} }
