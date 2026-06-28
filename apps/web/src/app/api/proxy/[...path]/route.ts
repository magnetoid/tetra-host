import { proxyBackendRequest } from "@/lib/api"
import { getSessionToken } from "@/lib/session"

type RouteContext = {
  params: Promise<{ path: string[] }>
}

async function handleProxy(request: Request, context: RouteContext) {
  const { path } = await context.params
  const token = await getSessionToken()
  const targetPath = path.join("/")
  return proxyBackendRequest(targetPath, request, token)
}

export async function GET(request: Request, context: RouteContext) {
  return handleProxy(request, context)
}

export async function POST(request: Request, context: RouteContext) {
  return handleProxy(request, context)
}

export async function PUT(request: Request, context: RouteContext) {
  return handleProxy(request, context)
}

export async function PATCH(request: Request, context: RouteContext) {
  return handleProxy(request, context)
}

export async function DELETE(request: Request, context: RouteContext) {
  return handleProxy(request, context)
}
