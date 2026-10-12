import { expect, test } from 'claude-code/testing'

import { extractCheckpointBlock } from './checkpoint-block'

const TICKS = '```'
const fenced = (body: string, info = 'superheroes-checkpoint', fence = TICKS) =>
  `${fence}${info}\n${body}\n${fence}\n`

test('no block: null', () => {
  expect(extractCheckpointBlock('')).toBeNull()
  expect(extractCheckpointBlock('Just prose.\n\nNo fences here.')).toBeNull()
})

test('one closed block: its body, no fences, no trailing newline', () => {
  expect(extractCheckpointBlock(`Reply.\n\n${fenced('line one\nline two')}`)).toBe('line one\nline two')
})

test('the body keeps inner blank lines and indentation', () => {
  expect(extractCheckpointBlock(fenced('a\n\n  b'))).toBe('a\n\n  b')
})

test('unclosed block: null', () => {
  expect(extractCheckpointBlock(`${TICKS}superheroes-checkpoint\nnotes\nmore notes\n`)).toBeNull()
})

test('a shorter fence line does not close a longer fence', () => {
  expect(extractCheckpointBlock(`${TICKS}\`superheroes-checkpoint\nnotes\n${TICKS}\n`)).toBeNull()
})

test('empty or whitespace-only body: null', () => {
  expect(extractCheckpointBlock(fenced(''))).toBeNull()
  expect(extractCheckpointBlock(fenced('  \n\t\n'))).toBeNull()
})

test('two blocks: the last wins', () => {
  const text = `${fenced('first')}\nmiddle prose\n\n${fenced('second')}`

  expect(extractCheckpointBlock(text)).toBe('second')
})

test('the last block wins even when it is the one left unclosed or empty', () => {
  expect(extractCheckpointBlock(`${fenced('first')}\n${TICKS}superheroes-checkpoint\nhalf\n`)).toBeNull()
  expect(extractCheckpointBlock(`${fenced('first')}\n${fenced('')}`)).toBeNull()
})

test('a longer fence may contain a three-backtick line', () => {
  const body = `before\n${TICKS}bash\necho hi\n${TICKS}\nafter`
  const text = `Intro\n\n\`\`\`\`superheroes-checkpoint\n${body}\n\`\`\`\`\n`

  expect(extractCheckpointBlock(text)).toBe(body)
})

test('a closing fence may be longer than the opening one', () => {
  expect(extractCheckpointBlock(`${TICKS}superheroes-checkpoint\nnotes\n\`\`\`\`\`\n`)).toBe('notes')
})

test('wrong info string: null', () => {
  expect(extractCheckpointBlock(fenced('notes', 'text'))).toBeNull()
  expect(extractCheckpointBlock(fenced('notes', ''))).toBeNull()
  expect(extractCheckpointBlock(fenced('notes', 'superheroes-checkpoint-v2'))).toBeNull()
  expect(extractCheckpointBlock(fenced('notes', 'superheroes-checkpoints'))).toBeNull()
  expect(extractCheckpointBlock(fenced('notes', 'superheroes-checkpoint extra'))).toBeNull()
})

test('a checkpoint fence quoted inside another fence is not a block', () => {
  const quoted = `\`\`\`\`markdown\n${fenced('quoted')}\`\`\`\`\n`

  expect(extractCheckpointBlock(quoted)).toBeNull()
  expect(extractCheckpointBlock(`${quoted}\n${fenced('real')}`)).toBe('real')
})

test('CRLF line endings parse the same', () => {
  expect(extractCheckpointBlock(fenced('a\nb').replace(/\n/g, '\r\n'))).toBe('a\nb')
})
