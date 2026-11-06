// Retain the same request key after a timeout; an edited form is a new request.
export function createSubmissionKey() {
  let signature = '',
    key = ''
  return {
    forPayload(payload: unknown) {
      const next = JSON.stringify(payload)
      if (!key || signature !== next) {
        signature = next
        key = crypto.randomUUID()
      }
      return key
    },
    reset() {
      signature = ''
      key = ''
    },
  }
}
