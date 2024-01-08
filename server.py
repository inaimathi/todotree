import tornado

import model


class JSONHandler(tornado.web.RequestHandler):
    def set_default_headers(self):
        self.set_header("Content-Type", "application/json")

    def json(self, data, status=None):
        if status is not None:
            self.set_status(status)
        self.write(json.dumps(data))

class HealthHandler(JSONHandler):
    def get(self):
        val = self.get_argument("value", None)
        res = {"status": "ok"}
        if val is not None:
            res["value"] = val
        self.json(res)

class TodoHandler(JSONHandler):
    def get(self):
        self.json({
            "status": "ok",
            "todos": model.todos()
        })


ROUTES = [
    (r"/v0/health", HealthHandler),
    (r"/v0/todo", TodoHandler)
]

async def main(port):
    global THREAD
    print("Setting up app...")
    app = tornado.web.Application(
        ROUTES,
        default_handler_class=TrapCard
    )
    print(f"  listening on {port}...")
    app.listen(port)
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main(8080))
