from . import menu, post_writer, common, humanizer, audit, comment, reply, hook_extractor, engagement, profile, planner  # more skill routers added in later tasks

routers = [menu.router, post_writer.router, common.router, humanizer.router, audit.router, comment.router, reply.router, hook_extractor.router, engagement.router, profile.router, planner.router]
