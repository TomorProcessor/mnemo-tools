export type GateKind =
  | 'impl'
  | 'build'
  | 'test'
  | 'test_files'
  | 'e2e'
  | 'e2e_coverage'
  | 'review'
  | 'smoke'
  | 'smoke_e2e'
  | 'scope_check'
  | 'rules'
  | 'lint'
  | 'spec_verify'
  | 'spec_coverage'
  | 'i18n_check'
  | 'design_fidelity'
  | 'required_components'
  | 'coverage_check'
  | 'merge'
  | 'terminal'

export type GateResult =
  | 'pass'
  | 'fail'
  | 'warn'
  | 'skip'
  | 'running'
  | null

export interface DowngradeEntry {
  from: string
  to: string
  reason: string
}

export interface AttemptNode {
  id: string
  attempt: number
  kind: GateKind
  runIndexForKind: number
  result: GateResult
  ms: number | null
  startedAt: string
  endedAt: string | null
  output?: string
  verdictSource?: string
  downgrades?: DowngradeEntry[]
  issueRefs?: string[]
  /** LLM cost/model info joined from /timeline session list. Present only
   * for nodes whose work was backed by a Claude call (impl, review,
   * spec-verify, etc.). Gate nodes that run non-LLM commands (build, test,
   * e2e) do not carry these fields. */
  model?: string
  inputTokens?: number
  outputTokens?: number
  cacheTokens?: number
}

export type AttemptOutcome = 'retry' | 'merged' | 'failed' | 'in-progress'
export type RetryReason = 'gate-fail' | 'merge-conflict' | 'replan' | 'reset-failed' | 'unknown'

export interface Attempt {
  n: number
  startedAt: string
  endedAt: string | null
  outcome: AttemptOutcome
  retryReason?: RetryReason
  nodes: AttemptNode[]
}

export type TerminalState = 'merged' | 'failed' | 'in-progress'

export interface AttemptGraph {
  attempts: Attempt[]
  terminal: TerminalState
  totalMs: number
  totalGateRuns: number
}

export interface VerdictSidecar {
  change: string
  session?: number
  gate?: string
  source?: string
  downgrades?: DowngradeEntry[]
}
