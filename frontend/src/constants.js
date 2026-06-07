// Agent-type groupings shared across pages.

// Chatter-family agent types run through the stateful /api/chat
// session API, not the one-shot /api/run endpoint.
export const CHATTER_TYPES = new Set([
  'chatter',
  'personality_chatter',
  'scene_chatter',
  'guarded_chatter',
  'guarded_scene_chatter',
])

export function isChatter(agentType) {
  return CHATTER_TYPES.has((agentType || '').toLowerCase())
}
