/**
 * The feature consumes the application-wide content contract. Keep this file
 * as a stable feature import path without maintaining a second document model.
 */
export * from "../../domain/content";
export { CONTENT_SCHEMA_VERSION as BOT_CONTENT_SCHEMA_VERSION } from "../../domain/content";

export type CompileDiagnostic = import("../../domain/content").ContentDiagnostic;
