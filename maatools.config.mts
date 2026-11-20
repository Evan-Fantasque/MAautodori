import type { FullConfig } from '@nekosu/maa-tools'

const config: FullConfig = {
  cwd: import.meta.dirname,
  maaVersion: '6.0.0-beta.3',
  interfacePath: 'assets/interface.json',
  check: {
    // Preserve MaaPipelineEditor workspace metadata in source files.
    override: { 'mpe-config': 'ignore' }
  }
}

export default config
