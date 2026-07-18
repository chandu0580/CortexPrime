import { GitHubDiscussion } from "./types"
import { GitHubClient } from "./GitHubClient"

const GITHUB_GRAPHQL = true

const createDiscussionQuery = `
  mutation($repoId: ID!, $title: String!, $body: String!, $categoryId: String!) {
    createDiscussion(input: { repositoryId: $repoId, title: $title, body: $body, categoryId: $categoryId }) {
      discussion {
        id number title body category { name } locked
        createdAt updatedAt
        author { login }
      }
    }
  }
`

const listDiscussionsQuery = `
  query($owner: String!, $repo: String!, $first: Int!) {
    repository(owner: $owner, name: $repo) {
      discussions(first: $first) {
        nodes {
          id number title body locked answerChosen
          comments { totalCount }
          category { name }
          author { login }
          createdAt updatedAt
        }
      }
    }
  }
`

function mapApiDiscussion(apiDisc: Record<string, unknown>, repositoryId: string): GitHubDiscussion {
  return {
    id: String(apiDisc.id),
    repositoryId,
    number: Number(apiDisc.number),
    title: String(apiDisc.title ?? ""),
    body: String(apiDisc.body ?? ""),
    author: (apiDisc.author as Record<string, unknown>)?.login as string ?? "",
    category: (apiDisc.category as Record<string, unknown>)?.name as string ?? (apiDisc as Record<string, unknown>).categoryName as string ?? "",
    locked: Boolean(apiDisc.locked),
    answerChosen: Boolean(apiDisc.answerChosen),
    comments: Number((apiDisc.comments as Record<string, unknown>)?.totalCount ?? apiDisc.comments ?? 0),
    createdAt: String(apiDisc.createdAt ?? apiDisc.created_at),
    updatedAt: String(apiDisc.updatedAt ?? apiDisc.updated_at),
  }
}

export const GitHubDiscussionManager = {
  async createDiscussion(
    repoId: string,
    title: string,
    body: string,
    categoryId: string,
  ): Promise<GitHubDiscussion> {
    const result = await GitHubClient.graphql<Record<string, unknown>>(createDiscussionQuery, { repoId, title, body, categoryId })
    if (result.success && result.data) {
      const disc = (result.data as Record<string, unknown>).createDiscussion as Record<string, unknown>
      const discussion = (disc?.discussion as Record<string, unknown>) ?? {}
      return mapApiDiscussion(discussion, repoId)
    }
    const now = new Date().toISOString()
    return { id: "", repositoryId: repoId, number: 0, title, body, author: "", category: categoryId, locked: false, answerChosen: false, comments: 0, createdAt: now, updatedAt: now }
  },

  async listDiscussions(owner: string, repo: string): Promise<GitHubDiscussion[]> {
    const result = await GitHubClient.graphql<Record<string, unknown>>(listDiscussionsQuery, { owner, repo, first: 100 })
    if (result.success && result.data) {
      const repoData = (result.data as Record<string, unknown>).repository as Record<string, unknown>
      const discussions = repoData?.discussions as Record<string, unknown>
      const nodes = discussions?.nodes as Record<string, unknown>[]
      return (nodes ?? []).map((n) => mapApiDiscussion(n, `${owner}/${repo}`))
    }
    return []
  },

  async lockDiscussion(owner: string, repo: string, discussionId: string): Promise<GitHubDiscussion | null> {
    const lockQuery = `
      mutation($discussionId: ID!) {
        lockLockable(input: { lockableId: $discussionId, lockReason: RESOLVED }) {
          lockable { ... on Discussion { id locked lockedReason } }
        }
      }
    `
    const result = await GitHubClient.graphql<Record<string, unknown>>(lockQuery, { discussionId })
    if (result.success && result.data) {
      const lockable = ((result.data as Record<string, unknown>).lockLockable as Record<string, unknown>)?.lockable as Record<string, unknown> ?? {}
      return { id: String(lockable.id), repositoryId: `${owner}/${repo}`, number: 0, title: "", body: "", author: "", category: "", locked: true, answerChosen: false, comments: 0, createdAt: new Date().toISOString(), updatedAt: new Date().toISOString() }
    }
    return null
  },

  async getDiscussion(owner: string, repo: string, discussionNumber: number): Promise<GitHubDiscussion | null> {
    const discussions = await this.listDiscussions(owner, repo)
    return discussions.find((d) => d.number === discussionNumber) ?? null
  },
}