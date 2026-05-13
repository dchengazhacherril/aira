from aira.reply_server import ReplyServer


def main():
    reply_server = ReplyServer()

    try:
        reply_server.start()
        print("Press Ctrl-C to stop.", flush=True)
        reply_server.monitor()
    except KeyboardInterrupt:
        print("Stopping reply server...", flush=True)
    finally:
        reply_server.stop()


if __name__ == "__main__":
    main()
