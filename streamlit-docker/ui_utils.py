import boto3
import streamlit as st
import datetime
import json
import math
import logging
import sys
from src.utils.bedrock_agent import Task

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('ui_utils')

def make_full_prompt(tasks, additional_instructions, processing_type="sequential"):
    """Build a full prompt from tasks and instructions."""
    logger.info(f"Building prompt with {len(tasks)} tasks")
    prompt = ''
    if processing_type == 'sequential':
        prompt += """
Please perform the following tasks sequentially. Be sure you do not 
perform any of the tasks in parallel. If a task will require information produced from a prior task, 
be sure to include the full text details as comprehensive input to the task.\n\n"""
    elif processing_type == "allow_parallel":
        prompt += """
Please perform as many of the following tasks in parallel where possible.
When a dependency between tasks is clear, execute those tasks in sequential order. 
If a task will require information produced from a prior task,
be sure to include the comprehensive text details as input to the task.\n\n"""

    for task_num, task in enumerate(tasks, 1):
        prompt += f"Task {task_num}. {task}\n"

    prompt += "\nBefore returning the final answer, review whether you have achieved the expected output for each task."

    if additional_instructions:
        prompt += f"\n{additional_instructions}"

    logger.debug(f"Final prompt: {prompt}")
    return prompt

def process_routing_trace(event, step, _sub_agent_name, _time_before_routing=None):
    """Process routing classifier trace events."""
    logger.info(f"Processing routing trace event: step={step}, sub_agent={_sub_agent_name}")
   
    _route = event['trace']['trace']['routingClassifierTrace']
    
    if 'modelInvocationInput' in _route:
        logger.info("Routing classifier input detected")
        container = st.container(border=True)                            
        container.markdown(f"""**Choosing a collaborator for this request...**""")
        return datetime.datetime.now(), step, _sub_agent_name, None, None
        
    if 'modelInvocationOutput' in _route and _time_before_routing:
        logger.info("Routing classifier output detected")
        _llm_usage = _route['modelInvocationOutput']['metadata']['usage']
        inputTokens = _llm_usage['inputTokens']
        outputTokens = _llm_usage['outputTokens']
        
        logger.info(f"Routing classifier tokens - input: {inputTokens}, output: {outputTokens}")
        _route_duration = datetime.datetime.now() - _time_before_routing

        _raw_resp_str = _route['modelInvocationOutput']['rawResponse']['content']
        _raw_resp = json.loads(_raw_resp_str)
        _classification = _raw_resp['content'][0]['text'].replace('<a>', '').replace('</a>', '')
        logger.info(f"Routing classification result: {_classification}")

        if _classification == "undecidable":
            text = f"No matching collaborator. Revert to 'SUPERVISOR' mode for this request."
        elif _classification in (_sub_agent_name, 'keep_previous_agent'):
            step = math.floor(step + 1)
            text = f"Continue conversation with previous collaborator"
        else:
            _sub_agent_name = _classification
            step = math.floor(step + 1)
            text = f"Use collaborator: '{_sub_agent_name}'"

        time_text = f"Intent classifier took {_route_duration.total_seconds():,.1f}s"
        container = st.container(border=True)                            
        container.write(text)
        container.write(time_text)
        
        logger.info(f"Routing decision: {text}")
        return step, _sub_agent_name, inputTokens, outputTokens

    logger.warning("Routing trace event didn't match expected patterns")
    return None

def process_orchestration_trace(event, agentClient, step):
    """Process orchestration trace events."""
    logger.info(f"Processing orchestration trace: step={step}")
    _orch = event['trace']['trace']['orchestrationTrace']
    inputTokens = 0
    outputTokens = 0
    
    if "invocationInput" in _orch:
        _input = _orch['invocationInput']
        logger.info("Orchestration invocation input detected")
        
        if 'knowledgeBaseLookupInput' in _input:
            kb_id = _input["knowledgeBaseLookupInput"]["knowledgeBaseId"]
            query = _input["knowledgeBaseLookupInput"]["text"].replace('$', '\$')
            logger.info(f"Knowledge base lookup: id={kb_id}, query={query}")
            
            with st.expander("Using knowledge base", False, icon=":material/plumbing:"):
                st.write("knowledge base id: " + kb_id)
                st.write("query: " + query)
                
        if "actionGroupInvocationInput" in _input:
            function = _input["actionGroupInvocationInput"]["function"]
            logger.info(f"Tool invocation: function={function}")
            
            with st.expander(f"Invoking Tool - {function}", False, icon=":material/plumbing:"):
                st.write("function : " + function)
                st.write("type: " + _input["actionGroupInvocationInput"]["executionType"])
                if 'parameters' in _input["actionGroupInvocationInput"]:
                    params = _input["actionGroupInvocationInput"]["parameters"]
                    logger.info(f"Tool parameters: {params}")
                    st.write("*Parameters*")
                    st.table({
                        'Parameter Name': [p["name"] for p in params],
                        'Parameter Value': [p["value"] for p in params]
                    })

        if 'codeInterpreterInvocationInput' in _input:
            logger.info("Code interpreter invocation detected")
            with st.expander("Code interpreter tool usage", False, icon=":material/psychology:"):
                gen_code = _input['codeInterpreterInvocationInput']['code']
                st.code(gen_code, language="python")
                    
    if "modelInvocationOutput" in _orch:
        logger.info("Model invocation output detected")
        if "usage" in _orch["modelInvocationOutput"]["metadata"]:
            inputTokens = _orch["modelInvocationOutput"]["metadata"]["usage"]["inputTokens"]
            outputTokens = _orch["modelInvocationOutput"]["metadata"]["usage"]["outputTokens"]
            logger.info(f"Token usage - input: {inputTokens}, output: {outputTokens}")
                    
    if "rationale" in _orch:
        logger.info("Rationale detected in orchestration trace")
        if "agentId" in event["trace"]:
            try:
                agentData = agentClient.get_agent(agentId=event["trace"]["agentId"])
                agentName = agentData["agent"]["agentName"]
                logger.info(f"Agent name: {agentName}")
                
                # Add check for callerChain
                chain = event["trace"].get("callerChain", [])  # Default to empty list if not present
                logger.info(f"Caller chain length: {len(chain)}")
                
                container = st.container(border=True)
                
                # Modify the chain length check to handle the case when callerChain might not exist
                if not chain or len(chain) <= 1:
                    step = math.floor(step + 1)
                    container.markdown(f"""#### Step  :blue[{round(step,2)}]""")
                    logger.info(f"Main step: {round(step,2)}")
                else:
                    step = step + 0.1
                    container.markdown(f"""###### Step {round(step,2)} Sub-Agent  :red[{agentName}]""")
                    logger.info(f"Sub-step: {round(step,2)} with sub-agent {agentName}")
                
                rationale_text = _orch["rationale"]["text"].replace('$', '\$')
                container.write(rationale_text)
                logger.debug(f"Rationale: {rationale_text[:100]}...")
            except Exception as e:
                logger.error(f"Error processing rationale: {e}")
                step = math.floor(step + 1)

    if "observation" in _orch:
        _obs = _orch['observation']
        logger.info("Observation detected in orchestration trace")
        
        if 'knowledgeBaseLookupOutput' in _obs:
            logger.info("Knowledge base lookup output detected")
            with st.expander("Knowledge Base Response", False, icon=":material/psychology:"):
                _refs = _obs['knowledgeBaseLookupOutput']['retrievedReferences']
                _ref_count = len(_refs)
                logger.info(f"Knowledge base returned {_ref_count} references")
                st.write(f"{_ref_count} references")
                for i, _ref in enumerate(_refs, 1):
                    st.write(f"  ({i}) {_ref['content']['text'][0:200]}...")

        if 'actionGroupInvocationOutput' in _obs:
            logger.info("Action group invocation output detected")
            with st.expander("Tool Response", False, icon=":material/psychology:"):
                tool_response = _obs['actionGroupInvocationOutput']['text'].replace('$', '\$')
                st.write(tool_response)
                logger.debug(f"Tool response: {tool_response[:100]}...")

        if 'codeInterpreterInvocationOutput' in _obs:
            logger.info("Code interpreter output detected")
            with st.expander("Code interpreter tool usage", False, icon=":material/psychology:"):
                if 'executionOutput' in _obs['codeInterpreterInvocationOutput']:
                    raw_output = _obs['codeInterpreterInvocationOutput']['executionOutput']
                    st.code(raw_output)
                    logger.debug(f"Code execution output: {raw_output[:100]}...")

                if 'executionError' in _obs['codeInterpreterInvocationOutput']:
                    error_text = _obs['codeInterpreterInvocationOutput']['executionError']
                    st.write(f"Code interpretation error: {error_text}")
                    logger.error(f"Code execution error: {error_text}")

                if 'files' in _obs['codeInterpreterInvocationOutput']:
                    files_generated = _obs['codeInterpreterInvocationOutput']['files']
                    st.write(f"Code interpretation files generated:\n{files_generated}")
                    logger.info(f"Code generated files: {files_generated}")

        if 'finalResponse' in _obs:
            logger.info("Final response detected")
            with st.expander("Agent Response", False, icon=":material/psychology:"):
                final_response = _obs['finalResponse']['text'].replace('$', '\$')
                st.write(final_response)
                logger.debug(f"Final response: {final_response[:100]}...")
            
    return step, inputTokens, outputTokens

def invoke_agent(input_text, session_id, task_yaml_content):
    """Main agent invocation and response processing."""
    from credential_manager import create_fresh_boto3_session, invalidate_boto3_cache, log_credential_status
    import time
    
    logger.info("=== AGENT INVOCATION STARTED ===")
    logger.info(f"Session ID: {session_id}")
    logger.info(f"Input text length: {len(input_text)} characters")
    
    # Log current credential status before attempting to create session
    log_credential_status()
    
    # Implement a more robust approach with credential validation
    session = None
    retry_count = 0
    max_retries = 3
    
    while retry_count < max_retries:
        try:
            logger.info(f"Credential validation attempt {retry_count + 1}/{max_retries}")
            
            # Invalidate any cached credentials first
            logger.info("Invalidating boto3 credential cache")
            invalidate_boto3_cache()
            
            # Create a fresh session with the latest credentials
            logger.info("Creating fresh boto3 session")
            session = create_fresh_boto3_session()
            
            if session is None:
                raise Exception("Failed to create boto3 session - session is None")
            
            logger.info("Successfully created boto3 session, testing with STS call")
            
            # Test the credentials with a lightweight API call
            sts_client = session.client('sts')
            start_time = time.time()
            identity = sts_client.get_caller_identity()
            sts_duration = time.time() - start_time
            
            # If we get here, credentials are valid
            account_id = identity.get('Account', 'unknown')
            user_id = identity.get('UserId', 'unknown')
            arn = identity.get('Arn', 'unknown')
            
            logger.info(f"✅ Successfully validated AWS credentials in {sts_duration:.2f}s")
            logger.info(f"Account ID: {account_id}")
            logger.info(f"User ID: {user_id}")
            logger.info(f"ARN: {arn}")
            break
            
        except Exception as e:
            retry_count += 1
            logger.warning(f"❌ Credential validation failed (attempt {retry_count}/{max_retries}): {str(e)}")
            
            if retry_count >= max_retries:
                logger.error("🚨 Failed to obtain valid credentials after multiple attempts")
                log_credential_status()  # Log final status before failing
                raise
                
            # Wait before retrying with exponential backoff
            sleep_time = 2 ** retry_count
            logger.info(f"⏳ Waiting {sleep_time} seconds before retrying...")
            time.sleep(sleep_time)
    
    # Now use the validated session
    logger.info("Creating Bedrock clients with validated session")
    client = session.client('bedrock-agent-runtime')
    agentClient = session.client('bedrock-agent')
    
    logger.info("✅ Bedrock clients created successfully")
    
    try:
        # Process tasks if any
        _tasks = []
        _bot_config = st.session_state['bot_config']
        logger.info(f"Bot config: {_bot_config['bot_name']}")
        
        for _task_name in task_yaml_content.keys():
            _curr_task = Task(_task_name, task_yaml_content, _bot_config['inputs'])
            _tasks.append(_curr_task)
            
        if len(_tasks) > 0:
            logger.info(f"Processing {len(_tasks)} tasks")
            additional_instructions = _bot_config.get('additional_instructions')
            messagesStr = make_full_prompt(_tasks, additional_instructions)
        else:
            logger.info("No tasks to process, using direct input text")
            messagesStr = input_text

        # Invoke agent
        try:
            logger.info(f"Invoking agent: {_bot_config['agent_id']} with alias: {_bot_config['agent_alias_id']}")
            
            if 'session_attributes' in _bot_config:
                logger.info("Using session attributes")
                session_state = {
                    "sessionAttributes": _bot_config['session_attributes']['sessionAttributes']
                }
                if 'promptSessionAttributes' in _bot_config['session_attributes']:
                    session_state['promptSessionAttributes'] = _bot_config['session_attributes']['promptSessionAttributes']

                response = client.invoke_agent(
                    agentId=_bot_config['agent_id'],
                    agentAliasId=_bot_config['agent_alias_id'],
                    sessionId=session_id,
                    sessionState=session_state,
                    inputText=messagesStr,
                    enableTrace=True
                )
            else:
                logger.info("No session attributes, using basic invocation")
                response = client.invoke_agent(
                    agentId=_bot_config['agent_id'],
                    agentAliasId=_bot_config['agent_alias_id'],
                    sessionId=session_id,
                    inputText=messagesStr,
                    enableTrace=True
                )
                
            logger.info("Agent invocation successful")
        except Exception as e:
            logger.error(f"Error invoking agent: {str(e)}", exc_info=True)
            raise e

        # Process response
        step = 0.0
        _sub_agent_name = " "
        _time_before_routing = None
        inputTokens = 0
        outputTokens = 0
        _total_llm_calls = 0
        
        with st.spinner("Processing ....."):
            logger.info("Starting to process agent response stream")
            
            # Check if completion exists in response
            if "completion" not in response:
                logger.error("No 'completion' field in response")
                logger.info(f"Response keys: {list(response.keys())}")
                logger.debug(f"Full response: {json.dumps(response, default=str)}")
                st.error("Error: No completion data in response")
                return "Error: No completion data in response"
            
            completion_count = 0
            for event in response.get("completion", []):
                completion_count += 1
                try:
                    # Debug logging
                    logger.debug(f"Event structure: {json.dumps(event, default=str)}")
                    
                    if "chunk" in event:
                        chunk_text = event["chunk"]["bytes"].decode("utf-8").replace('$', '\$')
                        logger.debug(f"Yielding chunk: {chunk_text[:50]}...")
                        yield chunk_text
                        
                    if "trace" in event:
                        logger.info("Processing trace data in event")
                        
                        if 'routingClassifierTrace' in event['trace']['trace']:
                            logger.info("Found routing classifier trace")
                            result = process_routing_trace(event, step, _sub_agent_name, _time_before_routing)
                            if result:
                                if len(result) == 5:
                                    _time_before_routing, step, _sub_agent_name, in_tokens, out_tokens = result
                                    if in_tokens and out_tokens:
                                        inputTokens += in_tokens
                                        outputTokens += out_tokens
                                        _total_llm_calls += 1
                                        logger.info(f"Updated token counts - input: {inputTokens}, output: {outputTokens}, calls: {_total_llm_calls}")
                                else:
                                    step, _sub_agent_name, in_tokens, out_tokens = result
                                    if in_tokens and out_tokens:
                                        inputTokens += in_tokens
                                        outputTokens += out_tokens
                                        _total_llm_calls += 1
                                        logger.info(f"Updated token counts - input: {inputTokens}, output: {outputTokens}, calls: {_total_llm_calls}")
                        
                        if "orchestrationTrace" in event["trace"]["trace"]:
                            logger.info("Found orchestration trace")
                            try:
                                result = process_orchestration_trace(event, agentClient, step)
                                if result:
                                    step, in_tokens, out_tokens = result
                                    if in_tokens and out_tokens:
                                        inputTokens += in_tokens
                                        outputTokens += out_tokens
                                        _total_llm_calls += 1
                                        logger.info(f"Updated token counts - input: {inputTokens}, output: {outputTokens}, calls: {_total_llm_calls}")
                            except Exception as e:
                                logger.error(f"Error processing orchestration trace: {str(e)}", exc_info=True)
                                continue

                except KeyError as e:
                    logger.warning(f"Missing key in event structure: {str(e)}")
                    continue
                except Exception as e:
                    logger.error(f"Error processing event: {str(e)}", exc_info=True)
                    continue

            logger.info(f"Processed {completion_count} completion events")
            logger.info(f"Final token counts - input: {inputTokens}, output: {outputTokens}, calls: {_total_llm_calls}")
            
            # Display token usage at the end
            container = st.container(border=True)
            container.markdown("Total Input Tokens : **" + str(inputTokens) + "**")
            container.markdown("Total Output Tokens : **" + str(outputTokens) + "**")
            container.markdown("Total LLM Calls : **" + str(_total_llm_calls) + "**")
            
            # Log final credential status after successful completion
            from credential_manager import log_credential_status
            logger.info("=== AGENT INVOCATION COMPLETED SUCCESSFULLY ===")
            log_credential_status()

    except Exception as e:
        logger.error(f"🚨 Error in invoke_agent: {str(e)}", exc_info=True)
        # Log credential status on error as well
        from credential_manager import log_credential_status
        logger.error("=== AGENT INVOCATION FAILED ===")
        log_credential_status()
        raise e
