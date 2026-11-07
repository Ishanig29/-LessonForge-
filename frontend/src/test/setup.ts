import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// Vitest globals are off, so React Testing Library's auto-cleanup must be wired manually.
afterEach(() => cleanup())
