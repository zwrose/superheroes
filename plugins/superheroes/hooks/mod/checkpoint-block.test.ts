import { expect, test } from 'claude-code/testing'

import { CHECKPOINT_INFO, extractCheckpointBlock } from './checkpoint-block'

const TICKS = '```'
const fenced = (body: string, info = CHECKPOINT_INFO, fence = TICKS) =>
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
  expect(extractCheckpointBlock(`${TICKS}${CHECKPOINT_INFO}\nnotes\nmore notes\n`)).toBeNull()
})

test('a shorter fence line does not close a longer fence', () => {
  expect(extractCheckpointBlock(`${TICKS}\`${CHECKPOINT_INFO}\nnotes\n${TICKS}\n`)).toBeNull()
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
  expect(extractCheckpointBlock(`${fenced('first')}\n${TICKS}${CHECKPOINT_INFO}\nhalf\n`)).toBeNull()
  expect(extractCheckpointBlock(`${fenced('first')}\n${fenced('')}`)).toBeNull()
})

test('a longer fence may contain a three-backtick line', () => {
  const body = `before\n${TICKS}bash\necho hi\n${TICKS}\nafter`
  const text = `Intro\n\n\`\`\`\`${CHECKPOINT_INFO}\n${body}\n\`\`\`\`\n`

  expect(extractCheckpointBlock(text)).toBe(body)
})

test('a closing fence may be longer than the opening one', () => {
  expect(extractCheckpointBlock(`${TICKS}${CHECKPOINT_INFO}\nnotes\n\`\`\`\`\`\n`)).toBe('notes')
})

test('wrong info string: null', () => {
  expect(extractCheckpointBlock(fenced('notes', 'text'))).toBeNull()
  expect(extractCheckpointBlock(fenced('notes', ''))).toBeNull()
  expect(extractCheckpointBlock(fenced('notes', `${CHECKPOINT_INFO}-v2`))).toBeNull()
  expect(extractCheckpointBlock(fenced('notes', `${CHECKPOINT_INFO}s`))).toBeNull()
  expect(extractCheckpointBlock(fenced('notes', `${CHECKPOINT_INFO} extra`))).toBeNull()
})

test('a checkpoint fence quoted inside another fence is not a block', () => {
  const quoted = `\`\`\`\`markdown\n${fenced('quoted')}\`\`\`\`\n`

  expect(extractCheckpointBlock(quoted)).toBeNull()
  expect(extractCheckpointBlock(`${quoted}\n${fenced('real')}`)).toBe('real')
})

test('a checkpoint fence quoted inside a tilde fence is not a block', () => {
  const quoted = `~~~markdown\n${fenced('quoted')}~~~\n`
  const longer = `~~~~markdown\n${fenced('quoted')}~~~~\n`

  expect(extractCheckpointBlock(quoted)).toBeNull()
  expect(extractCheckpointBlock(longer)).toBeNull()
  expect(extractCheckpointBlock(`${quoted}\n${fenced('real')}`)).toBe('real')
  // a backtick line does not close a tilde fence, nor a tilde line a backtick fence
  expect(extractCheckpointBlock(`~~~markdown\n\`\`\`\n${fenced('quoted')}~~~\n`)).toBeNull()
  expect(extractCheckpointBlock(`\`\`\`\`markdown\n~~~\n${fenced('quoted')}\`\`\`\`\n`)).toBeNull()
})

test('a checkpoint fence inside a tilde fence left unclosed at the end of the reply is not a block', () => {
  // an unclosed fence runs to the end of the reply, so the example is code, not a block
  expect(extractCheckpointBlock(`~~~markdown\n${fenced('quoted')}`)).toBeNull()
  expect(extractCheckpointBlock(`~~~~markdown\n${fenced('quoted')}`)).toBeNull()
})

test('CRLF line endings parse the same', () => {
  expect(extractCheckpointBlock(fenced('a\nb').replace(/\n/g, '\r\n'))).toBe('a\nb')
})

test('the block must end the reply: any non-blank line after the closing fence gives null', () => {
  expect(extractCheckpointBlock(`${fenced('example notes')}This is only an example.\n`)).toBeNull()
  expect(extractCheckpointBlock(`${fenced('example notes')}\n\nTrailing prose`)).toBeNull()
  expect(extractCheckpointBlock(`${fenced('example notes')}\`\`\`bash\necho hi\n\`\`\`\n`)).toBeNull()
  expect(extractCheckpointBlock(`${fenced('first')}after\n${fenced('second')}`)).toBe('second')
})

test('trailing blank lines and whitespace after the closing fence are fine', () => {
  expect(extractCheckpointBlock(`${fenced('notes')}\n  \n\t\n`)).toBe('notes')
  expect(extractCheckpointBlock(`${fenced('notes').replace(/\n/g, '\r\n')}\r\n`)).toBe('notes')
})
