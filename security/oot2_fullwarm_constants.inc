// Tool-only tracking of the public setters used by nxnative. Never installed
// into the app: ordinary builds keep the original setters and copy operation.
static int g_full_export;
static char full_cv_tag;
static NSMutableDictionary *full_cv_records;
// Metal copies specialized descriptors when assigning them to pipelines. Use
// the same public value identity as native arch_key; associated objects alone
// do not survive those copies. Include both hash and the value description.
static NSString *full_cv_key(MTLFunctionConstantValues *cv) {
    NSString *description = cv.description;
    NSRange nl = [description rangeOfString:@"\n"];
    if (nl.location == NSNotFound) { fprintf(stderr, "Missing constant value description\n"); abort(); }
    return [NSString stringWithFormat:@"%lu:%@", (unsigned long)cv.hash, [description substringFromIndex:nl.location]];
}
static NSDictionary *full_cv_values(MTL4SpecializedFunctionDescriptor *descriptor) {
    NSDictionary *values = objc_getAssociatedObject(descriptor, &full_cv_tag);
    if (!values && descriptor.constantValues) values = full_cv_records[full_cv_key(descriptor.constantValues)];
    return values;
}
static void full_cv_set(MTLFunctionConstantValues *cv, const void *value, MTLDataType type, NSUInteger index) {
    [cv setConstantValue:value type:type atIndex:index];
    if (!g_full_export) return;
    NSString *kind = nil; NSNumber *number = nil;
    if (type == MTLDataTypeBool) { kind = @"ConstantBool"; number = @(*(const bool *)value); }
    else if (type == MTLDataTypeInt) { kind = @"ConstantInt"; number = @(*(const int32_t *)value); }
    else { fprintf(stderr, "Unsupported full-prewarm function constant type %lu\n", (unsigned long)type); abort(); }
    NSMutableDictionary *values = objc_getAssociatedObject(cv, &full_cv_tag);
    if (!values) { values = [NSMutableDictionary dictionary]; objc_setAssociatedObject(cv, &full_cv_tag, values, OBJC_ASSOCIATION_RETAIN_NONATOMIC); }
    values[@(index)] = @{@"id_type": @"FunctionConstantIndex", @"id": @{@"data": @(index)}, @"value_type": kind, @"value": @{@"data": number}};
}
static void full_cv_bind(MTL4SpecializedFunctionDescriptor *descriptor, MTLFunctionConstantValues *cv) {
    descriptor.constantValues = cv;
    if (g_full_export) {
        NSDictionary *values = [objc_getAssociatedObject(cv, &full_cv_tag) copy];
        if (!values) values = @{};
        if (!full_cv_records) full_cv_records = [NSMutableDictionary dictionary];
        NSString *key = full_cv_key(descriptor.constantValues);
        NSDictionary *previous = full_cv_records[key];
        if (previous && ![previous isEqual:values]) { fprintf(stderr, "Conflicting function constant identity\n"); abort(); }
        full_cv_records[key] = values;
        objc_setAssociatedObject(descriptor, &full_cv_tag, values, OBJC_ASSOCIATION_RETAIN_NONATOMIC);
    }
}
static MTLFunctionConstantValues *full_cv_copy_from(MTL4SpecializedFunctionDescriptor *descriptor) {
    MTLFunctionConstantValues *copy = [descriptor.constantValues copy];
    if (g_full_export) {
        NSMutableDictionary *values = [full_cv_values(descriptor) mutableCopy];
        if (values) objc_setAssociatedObject(copy, &full_cv_tag, values, OBJC_ASSOCIATION_RETAIN_NONATOMIC);
    }
    return copy;
}
