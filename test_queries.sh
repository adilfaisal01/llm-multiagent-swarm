#!/bin/bash
# Swarm test suite — 5 queries of varying difficulty
cd /mnt/E/github-projects/llm-multiagent-swarm

QUERIES=(
  "What is the capital of France and what is its population?"
  "Explain the key differences between REST and GraphQL APIs for a junior developer"
  "What are the economic implications of the US-China trade war on semiconductor supply chains?"
  "Why did Blockbuster fail while Netflix succeeded? Analyze the business strategy differences"
  "How does the Linux kernel handle memory management with NUMA architectures?"
)

LABELS=(
  "01-easy-capital"
  "02-medium-rest-vs-graphql"
  "03-hard-semiconductor-trade-war"
  "04-fun-blockbuster-vs-netflix"
  "05-deep-linux-numa"
)

for i in "${!QUERIES[@]}"; do
  echo ""
  echo "═══════════════════════════════════════════════════"
  echo "  TEST ${LABELS[$i]}"
  echo "  Query: ${QUERIES[$i]}"
  echo "═══════════════════════════════════════════════════"
  echo ""
  
  python3 swarm2.py --goal "${QUERIES[$i]}" --mix 2>&1 | tee "/tmp/swarm-${LABELS[$i]}.log"
  
  echo ""
  echo "  ✓ Done with ${LABELS[$i]}"
  echo "  Log: /tmp/swarm-${LABELS[$i]}.log"
  echo ""
done

echo ""
echo "═══════════════════════════════════════════════════"
echo "  ALL 5 TESTS COMPLETE"
echo "═══════════════════════════════════════════════════"
