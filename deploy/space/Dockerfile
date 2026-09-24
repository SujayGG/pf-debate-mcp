# Free public pf-debate server on a Hugging Face Space (Docker SDK, free CPU tier).
# The card library is downloaded at boot from the SujayG5/pf-debate-library dataset (no persistent disk needed).
FROM python:3.12-slim
ARG REF=main
RUN pip install --no-cache-dir uv \
 && uv pip install --system --no-cache "pf-debate-mcp @ https://github.com/SujayGG/pf-debate-mcp/archive/${REF}.tar.gz"
# One process only: hosted cuts live in this process's memory (threads serve concurrent students).
ENV PF_DEBATE_HOME=/tmp/pf-debate \
    PORT=7860 \
    WEB_CONCURRENCY=1 \
    PUBLIC_URL=https://debate.peshcompsci.org \
    ALLOWED_HOSTS=debate.peshcompsci.org,sujayg5-pf-debate.hf.space
EXPOSE 7860
CMD ["pf-debate-mcp", "serve-http"]
