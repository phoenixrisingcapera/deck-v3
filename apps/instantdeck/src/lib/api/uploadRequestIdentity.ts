const UUID_V4_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

export function createUploadRequestId(
  cryptoSource: Pick<Crypto, 'randomUUID'> | null | undefined = globalThis.crypto
): string {
  if (!cryptoSource || typeof cryptoSource.randomUUID !== 'function') {
    throw new Error('Secure upload identity is unavailable in this browser.');
  }
  const id = cryptoSource.randomUUID().toLowerCase();
  if (!UUID_V4_PATTERN.test(id)) {
    throw new Error('Secure upload identity generation failed.');
  }
  return `upload-${id}`;
}
