"""OpenAI Q&A with Retrieval Augmented Generation (RAG)."""

import os
import json
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_mongodb import MongoDBAtlasVectorSearch
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.chains.chat_vector_db import prompts
from dotenv import load_dotenv
from kafka import KafkaConsumer,KafkaProducer

load_dotenv()

# Create a Kafka consumer
consumer = KafkaConsumer(
    'prompts',  
    bootstrap_servers=os.getenv("REDPANDA_SERVER"),  
    security_protocol="SASL_SSL",
    sasl_mechanism="SCRAM-SHA-256",
    sasl_plain_username=os.getenv("REDPANDA_USER"),
    sasl_plain_password=os.getenv("REDPANDA_PWD"),
    group_id='inference-group',  
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))  # decode messages from bytes to JSON
)

# Create a Kafka producer
producer = KafkaProducer(
    bootstrap_servers=os.getenv("REDPANDA_SERVER"),
    security_protocol="SASL_SSL",
    sasl_mechanism="SCRAM-SHA-256",
    sasl_plain_username=os.getenv("REDPANDA_USER"),
    sasl_plain_password=os.getenv("REDPANDA_PWD"),
    value_serializer=lambda x: json.dumps(x).encode('utf-8'),
)
vector_search = MongoDBAtlasVectorSearch.from_connection_string(
        os.getenv("MONGODB_URI"),
        os.getenv("DB_NAME")+ "." + os.getenv("COLLECTION_NAME"),
        OpenAIEmbeddings(model=os.getenv("OPENAI_EMBEDDING_MODE"),openai_api_key=os.getenv("OPENAI_API_KEY"), openai_organization=os.getenv("OPENAI_ORGANIZATION_ID")), 
        index_name=os.getenv("INDEX_NAME"),
    )

def main():
    try:
        for message in consumer:
            # Extract the question from the message value
            print(f"Received from Device: {message.value} ")
            device_id = message.value['device_id']
            question = message.value['prompt']
            assigned_topic = message.value['assigned_topic']
            print(f"Received from Device id: {device_id} - Prompt: {question}")

            # Query the data with the question
            answer = doRAG(question)

            # Create the response JSON
            response_message = {
                "device_id": device_id,
                "response": answer
            }
            producer.send(assigned_topic, response_message)

    except KeyboardInterrupt:
        pass

    finally:
        # Close the consumer
        consumer.close()

def doRAG(query):
    top_k = 10

    results = vector_search.similarity_search_with_score(
        query=query,
        k=top_k
    )

    print("\nSource documents:")
    for r in results:
        print(f"score: {r[1]}, text: {r[0].page_content[:500]}... \n\n")

    # Retrieve and Generate
    retriever = vector_search.as_retriever(
        search_type="similarity",
        search_kwargs={"k": top_k, "score_threshold": 0.75}
    )
    llm = ChatOpenAI(model=os.getenv("OPENAI_MODEL"),openai_api_key=os.getenv("OPENAI_API_KEY"), openai_organization=os.getenv("OPENAI_ORGANIZATION_ID"))


    def format_docs(docs):
        return "\n".join(doc.page_content for doc in docs)

    # Build the RAG chain
    rag_chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompts.QA_PROMPT
        | llm
        | StrOutputParser()
    )

    answer = rag_chain.invoke(query)
    print(f"\n Augmented answer: {answer}")

    return answer

if __name__ == "__main__":
    main()