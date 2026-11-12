// Public feasibility probe: open an iOS IR library on the runner and serialize
// a render base. A missing compiler is a real limitation, never a passing skip.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>

static id<MTLLibrary> library(id<MTLDevice> device, NSString *path) {
    NSData *bytes = [NSData dataWithContentsOfFile:path];
    if (!bytes) return nil;
    dispatch_data_t data = dispatch_data_create(bytes.bytes, bytes.length, nil, DISPATCH_DATA_DESTRUCTOR_DEFAULT);
    NSError *error = nil;
    id<MTLLibrary> lib = [device newLibraryWithData:data error:&error];
    if (!lib) fprintf(stderr, "Unified library load failed: %s\n", error.localizedDescription.UTF8String);
    return lib;
}

int main(int argc, char **argv) { @autoreleasepool {
    if (argc != 4) return 2;
    id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
    printf("Probe GPU: %s; Metal4 family=%d\n", dev.name.UTF8String, [dev supportsFamily:MTLGPUFamilyMetal4]);
    id<MTLLibrary> v = library(dev, @(argv[1])), f = library(dev, @(argv[2]));
    if (!v || !f) return 3;
    puts("Unified iOS libraries opened on macOS.");
    MTL4PipelineDataSetSerializerDescriptor *sd = [MTL4PipelineDataSetSerializerDescriptor new];
    sd.configuration = MTL4PipelineDataSetSerializerConfigurationCaptureDescriptors;
    id<MTL4PipelineDataSetSerializer> ser = [dev newPipelineDataSetSerializerWithDescriptor:sd];
    MTL4CompilerDescriptor *cd = [MTL4CompilerDescriptor new]; cd.pipelineDataSetSerializer = ser;
    NSError *error = nil; id<MTL4Compiler> compiler = [dev newCompilerWithDescriptor:cd error:&error];
    if (!compiler) { fprintf(stderr, "No Metal4 compiler: %s\n", error.localizedDescription.UTF8String); return 4; }
    MTL4LibraryFunctionDescriptor *vf = [MTL4LibraryFunctionDescriptor new], *ff = [MTL4LibraryFunctionDescriptor new];
    vf.library = v; vf.name = @"vmain"; ff.library = f; ff.name = @"fmain";
    MTL4RenderPipelineDescriptor *desc = [MTL4RenderPipelineDescriptor new];
    desc.vertexFunctionDescriptor = vf; desc.fragmentFunctionDescriptor = ff;
    for (int i = 0; i < 8; i++) {
        MTL4RenderPipelineColorAttachmentDescriptor *a = desc.colorAttachments[i];
        a.pixelFormat = MTLPixelFormatUnspecialized; a.writeMask = MTLColorWriteMaskUnspecialized; a.blendingState = MTL4BlendStateUnspecialized;
        a.sourceRGBBlendFactor = a.destinationRGBBlendFactor = a.sourceAlphaBlendFactor = a.destinationAlphaBlendFactor = MTLBlendFactorUnspecialized;
        a.rgbBlendOperation = a.alphaBlendOperation = MTLBlendOperationUnspecialized;
    }
    id pipeline = [compiler newRenderPipelineStateWithDescriptor:desc compilerTaskOptions:nil error:&error];
    NSData *script = [ser serializeAsPipelinesScriptWithError:&error];
    if (script) [script writeToFile:@(argv[3]) atomically:YES];
    printf("Probe pipeline=%d script_bytes=%lu\n", pipeline != nil, (unsigned long)script.length);
    if (!pipeline || !script.length) { fprintf(stderr, "Capture failed: %s\n", error.localizedDescription.UTF8String); return 5; }
    return 0;
} }
