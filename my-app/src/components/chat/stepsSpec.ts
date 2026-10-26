// The ```steps block format (see StepsBlock).
export type StepsSpec = {
  title?: string
  steps: { title: string; detail?: string }[]
}

export function parseSteps(source: string): StepsSpec | null {
  try {
    const spec = JSON.parse(source) as StepsSpec
    if (!Array.isArray(spec.steps) || !spec.steps.length) return null
    if (!spec.steps.every(step => step && typeof step.title === 'string')) return null
    return spec
  } catch {
    return null
  }
}
