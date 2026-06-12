from . import menu, post_writer, common, humanizer  # more skill routers added in later tasks

routers = [menu.router, post_writer.router, common.router, humanizer.router]
