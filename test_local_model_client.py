import unittest
from unittest.mock import patch, MagicMock, mock_open
import json
import os
import sys

# Ensure local_model_client can be imported.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from local_model_client import LocalModelClient
from llama_index.core.llms import CompletionResponse
from llama_index.core.schema import ImageDocument


class TestLocalModelClient(unittest.TestCase):

    @patch('local_model_client.os.path.exists', return_value=True) # Assume paths always exist for these tests
    @patch('local_model_client.LlamaCPP')
    def test_initialization_success_with_clip(self, MockLlamaCPP, mock_path_exists):
        mock_llamacpp_instance = MockLlamaCPP.return_value
        client = LocalModelClient(model_path="dummy.gguf", clip_model_path="clip.gguf", model_name="qwen_test", temperature=0.2, max_new_tokens=1000, context_window=2000, n_gpu_layers=10, verbose=True)

        MockLlamaCPP.assert_called_once_with(
            model_path="dummy.gguf",
            clip_model_path="clip.gguf",
            temperature=0.2,
            max_new_tokens=1000,
            context_window=2000,
            generate_kwargs={},
            model_kwargs={"n_gpu_layers": 10},
            verbose=True
        )
        self.assertEqual(client.llm, mock_llamacpp_instance)
        self.assertTrue(client.is_multimodal)
        self.assertEqual(client.model_name, "qwen_test")

    @patch('local_model_client.os.path.exists', return_value=True)
    @patch('local_model_client.LlamaCPP')
    def test_initialization_success_no_clip(self, MockLlamaCPP, mock_path_exists):
        mock_llamacpp_instance = MockLlamaCPP.return_value
        client = LocalModelClient(model_path="dummy.gguf") # No clip_model_path

        MockLlamaCPP.assert_called_once_with(
            model_path="dummy.gguf",
            # clip_model_path should not be in kwargs if None
            temperature=0.1, # default
            max_new_tokens=2048, # default
            context_window=3900, # default
            generate_kwargs={},
            model_kwargs={"n_gpu_layers": -1}, # default
            verbose=False # default
        )
        self.assertFalse(client.is_multimodal)

    @patch('local_model_client.os.path.exists', return_value=False)
    @patch('local_model_client.LlamaCPP')
    def test_initialization_model_path_not_found(self, MockLlamaCPP, mock_path_exists):
        with self.assertRaisesRegex(FileNotFoundError, "Main GGUF model file not found"):
            LocalModelClient(model_path="nonexistent.gguf")

    @patch('local_model_client.os.path.exists', side_effect=[True, False]) # Main model exists, clip does not
    @patch('local_model_client.LlamaCPP')
    def test_initialization_clip_path_not_found(self, MockLlamaCPP, mock_path_exists):
        with self.assertRaisesRegex(FileNotFoundError, "CLIP model file not found"):
            LocalModelClient(model_path="dummy.gguf", clip_model_path="nonexistent_clip.gguf")

    @patch('local_model_client.os.path.exists', return_value=True)
    @patch('local_model_client.LlamaCPP', side_effect=Exception("LlamaCPP Init Failed"))
    def test_initialization_llamacpp_failure(self, MockLlamaCPP, mock_path_exists):
        with self.assertRaisesRegex(RuntimeError, "Failed to initialize LlamaCPP: LlamaCPP Init Failed"):
            LocalModelClient(model_path="dummy.gguf")

    @patch('local_model_client.os.path.exists', return_value=True)
    @patch('local_model_client.LlamaCPP')
    def test_generate_steps_for_todo_success_json_list(self, MockLlamaCPP, mock_path_exists):
        mock_llm = MockLlamaCPP.return_value
        # LlamaCPP's .complete returns CompletionResponse
        mock_llm.complete.return_value = CompletionResponse(text='["Step 1", "Step 2", "Step 3"]')

        client = LocalModelClient(model_path="dummy.gguf")
        steps = client.generate_steps_for_todo("Some objective")

        self.assertEqual(steps, ["Step 1", "Step 2", "Step 3"])
        mock_llm.complete.assert_called_once()

    @patch('local_model_client.os.path.exists', return_value=True)
    @patch('local_model_client.LlamaCPP')
    def test_generate_steps_for_todo_success_json_dict_with_steps_key(self, MockLlamaCPP, mock_path_exists):
        mock_llm = MockLlamaCPP.return_value
        mock_llm.complete.return_value = CompletionResponse(text='{"steps": ["Step A", "Step B"]}')
        client = LocalModelClient(model_path="dummy.gguf")
        steps = client.generate_steps_for_todo("Another objective")
        self.assertEqual(steps, ["Step A", "Step B"])

    @patch('local_model_client.os.path.exists', return_value=True)
    @patch('local_model_client.LlamaCPP')
    def test_generate_steps_for_todo_non_json_fallback(self, MockLlamaCPP, mock_path_exists):
        mock_llm = MockLlamaCPP.return_value
        mock_llm.complete.return_value = CompletionResponse(text="- Step X\n- Step Y\n-Step Z ") # Added extra non-uniform step
        client = LocalModelClient(model_path="dummy.gguf")
        steps = client.generate_steps_for_todo("Fallback objective")
        self.assertEqual(steps, ["Step X", "Step Y", "Step Z"])

    @patch('local_model_client.os.path.exists', return_value=True)
    @patch('local_model_client.LlamaCPP')
    def test_generate_steps_for_todo_empty_response(self, MockLlamaCPP, mock_path_exists):
        mock_llm = MockLlamaCPP.return_value
        mock_llm.complete.return_value = CompletionResponse(text="")
        client = LocalModelClient(model_path="dummy.gguf")
        steps = client.generate_steps_for_todo("some objective")
        self.assertEqual(steps, [f"Could not generate or parse steps. Raw: "])


    @patch('local_model_client.os.path.exists', return_value=True)
    @patch('local_model_client.open', new_callable=mock_open)
    @patch('local_model_client.os.remove')
    @patch('local_model_client.ImageDocument')
    @patch('local_model_client.LlamaCPP')
    def test_analyze_and_decide_success_with_image(self, MockLlamaCPP, MockImageDocument, mock_os_remove, mock_file_open, mock_os_exists_specific):
        # This mock_os_exists is for the one inside _create_temporary_image_file and _cleanup
        mock_os_exists_specific.return_value = True # for os.path.exists(temp_dir) and os.path.exists(img_path)

        mock_llm = MockLlamaCPP.return_value
        mock_llm.complete.return_value = CompletionResponse(
            text='{"thinking": "Clicked button", "action": "click(1)"}'
        )
        mock_image_doc_instance = MockImageDocument.return_value

        client = LocalModelClient(model_path="dummy.gguf", clip_model_path="clip.gguf")
        result = client.analyze_and_decide(image_base64="dummybase64", user_objective="obj", current_task="task")

        self.assertEqual(result, {"thinking": "Clicked button", "action": "click(1)"})
        # Check temp file name creation (it's random, so check if called)
        # And that ImageDocument was called with this path
        self.assertTrue(mock_file_open.call_args[0][0].startswith(os.path.join("temp_images", "")))
        image_path_used = mock_file_open.call_args[0][0]
        MockImageDocument.assert_called_with(image_path=image_path_used)
        mock_llm.complete.assert_called_with(unittest.mock.ANY, image_documents=[mock_image_doc_instance])
        mock_os_remove.assert_called_with(image_path_used)


    @patch('local_model_client.os.path.exists', return_value=True)
    @patch('local_model_client.LlamaCPP')
    def test_analyze_and_decide_no_clip_model(self, MockLlamaCPP, mock_path_exists):
        client = LocalModelClient(model_path="dummy.gguf") # No clip_model_path
        result = client.analyze_and_decide(image_base64="dummybase64", user_objective="obj")
        self.assertEqual(result, {"thinking": "Error: Client not configured for multi-modal analysis (CLIP model path missing).", "action": ""})

    @patch('local_model_client.os.path.exists', return_value=True)
    @patch('local_model_client.LlamaCPP')
    def test_analyze_and_decide_json_parsing_error(self, MockLlamaCPP, mock_path_exists):
        mock_llm = MockLlamaCPP.return_value
        mock_llm.complete.return_value = CompletionResponse(text="not a json")
        # Need clip path to get past the first check for multimodal
        client = LocalModelClient(model_path="dummy.gguf", clip_model_path="clip.gguf")
        # Assume image handling is fine (mocked if necessary for this specific test focus)
        with patch.object(client, '_create_temporary_image_file', return_value="temp.png"), \
             patch.object(client, '_cleanup_temporary_image_file'):
            result = client.analyze_and_decide(image_base64="dummybase64", user_objective="obj")
        self.assertIn("Error: Could not parse JSON response. Raw: not a json", result["thinking"])
        self.assertEqual(result["action"], "")

    @patch('local_model_client.os.path.exists', return_value=True)
    @patch('local_model_client.open', new_callable=mock_open)
    @patch('local_model_client.os.remove')
    @patch('local_model_client.ImageDocument')
    @patch('local_model_client.LlamaCPP')
    def test_analyze_state_vision_success_bool_parsing(self, MockLlamaCPP, MockImageDocument, mock_os_remove, mock_file_open, mock_os_exists_specific):
        mock_os_exists_specific.return_value = True
        mock_llm = MockLlamaCPP.return_value
        mock_llm.complete.return_value = CompletionResponse(
            text='{"error": null, "task_completed": "true", "objective_completed": "False", "summary": "Summary here"}'
        )
        mock_image_doc_instance = MockImageDocument.return_value

        client = LocalModelClient(model_path="dummy.gguf", clip_model_path="clip.gguf")
        result = client.analyze_state_vision(image_base64="dummybase64", current_task="task", objective="obj")

        self.assertIsNone(result["error"]) # null from JSON should become None
        self.assertTrue(result["task_completed"])
        self.assertFalse(result["objective_completed"])
        self.assertEqual(result["summary"], "Summary here")
        image_path_used = mock_file_open.call_args[0][0] # Get the path used for image
        MockImageDocument.assert_called_with(image_path=image_path_used)
        mock_llm.complete.assert_called_with(unittest.mock.ANY, image_documents=[mock_image_doc_instance])
        mock_os_remove.assert_called_with(image_path_used)

    @patch('local_model_client.os.path.exists', return_value=True)
    @patch('local_model_client.LlamaCPP')
    def test_analyze_state_vision_no_clip_model(self, MockLlamaCPP, mock_path_exists):
        client = LocalModelClient(model_path="dummy.gguf") # No clip_model_path
        result = client.analyze_state_vision(image_base64="dummybase64", current_task="task", objective="obj")
        self.assertEqual(result["error"], "Client not configured for multi-modal analysis (CLIP model path missing).")
        self.assertFalse(result["task_completed"])

if __name__ == '__main__':
    unittest.main()
```
