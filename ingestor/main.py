from ingestor import IngestorService

# entrypoint for the ingestor server
def run_ingestor():
    ingestor_srv = IngestorService()
    ingestor_srv.start()

if __name__ == '__main__':
    run_ingestor()

