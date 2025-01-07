import json
import pandas as pd
from typing import Dict, List, Union
import re
from pathlib import Path
from tqdm import tqdm
from math import sqrt
import ssl
import nltk


class WikiSectionReadabilityCalculator:
    def __init__(self):
        try:
            _create_unverified_https_context = ssl._create_unverified_context
        except AttributeError:
            pass
        else:
            ssl._create_default_https_context = _create_unverified_https_context

        try:
            nltk.download('punkt', quiet=True)
        except:
            print("Warning: NLTK download failed. Using fallback tokenizer.")
            self.use_fallback_tokenizer = True
        else:
            self.use_fallback_tokenizer = False


    def simple_sentence_tokenize(self, text: str) -> List[str]:
        """
        Fallback sentence tokenizer using regex.
        """
        # Split on period, exclamation mark, or question mark followed by space and uppercase letter
        sentences = re.split(r'[.!?]+\s+(?=[A-Z])', text)
        # Handle the last sentence that might not end with a capital letter
        if sentences:
            last_split = re.split(r'[.!?]+\s*', sentences[-1])
            sentences = sentences[:-1] + [s for s in last_split if s]
        return [s.strip() for s in sentences if s.strip()]

    def simple_word_tokenize(self, text: str) -> List[str]:
        """
        Fallback word tokenizer using regex.
        """
        # Split on whitespace and remove punctuation
        return [word.strip(".,!?()[]{}\"'") for word in text.split()]

    def load_wiki_json(self, file_path: Union[str, Path]) -> Dict:
        """
        Load Wikipedia articles from JSON format.
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def extract_section_texts(self, article_data: Dict) -> Dict[str, List[str]]:
        """
        Extract text from nested section structure.
        """
        sections_text = {}

        for section in article_data.get('sections', []):
            for heading, content in section.items():
                # Get main section text
                section_texts = content.get('text', [])
                sections_text[heading] = section_texts

                # Get subheading texts
                for subheading, subcontent in content.get('subheadings', {}).items():
                    subheading_texts = subcontent.get('text', [])
                    sections_text[f"{heading} -> {subheading}"] = subheading_texts

        return sections_text

    def calculate_text_metrics(self, text: str) -> Dict:
        """
        Calculate basic text metrics with robust error handling.
        """
        try:
            if not text or not isinstance(text, str):
                return self._get_empty_metrics()

            # Clean the text
            text = re.sub(r'\$.*?\$', '', text)  # Remove LaTeX formulas
            text = re.sub(r'\s+', ' ', text).strip()

            # Tokenize text
            if self.use_fallback_tokenizer:
                sentences = self.simple_sentence_tokenize(text)
                words = self.simple_word_tokenize(text)
            else:
                try:
                    sentences = nltk.sent_tokenize(text)
                    words = nltk.word_tokenize(text)
                except:
                    sentences = self.simple_sentence_tokenize(text)
                    words = self.simple_word_tokenize(text)

            # Filter words
            words = [word.lower() for word in words if word.isalnum()]

            # Check for empty text after processing
            if not words or not sentences:
                return self._get_empty_metrics()

            # Calculate metrics with safety checks
            word_count = len(words)
            sentence_count = len(sentences)

            syllable_counts = [self._count_syllables(word) for word in words]
            total_syllables = sum(syllable_counts)
            complex_words = sum(1 for count in syllable_counts if count >= 3)
            char_count = sum(len(word) for word in words)

            # Safely calculate averages
            avg_words_per_sentence = word_count / max(1, sentence_count)
            avg_syllables_per_word = total_syllables / max(1, word_count)
            avg_chars_per_word = char_count / max(1, word_count)

            return {
                'word_count': word_count,
                'sentence_count': sentence_count,
                'syllable_count': total_syllables,
                'complex_word_count': complex_words,
                'char_count': char_count,
                'avg_words_per_sentence': avg_words_per_sentence,
                'avg_syllables_per_word': avg_syllables_per_word,
                'avg_chars_per_word': avg_chars_per_word
            }
        except Exception as e:
            print(f"Error in calculate_text_metrics: {str(e)}")
            return self._get_empty_metrics()

    def _get_empty_metrics(self) -> Dict:
        """
        Return empty metrics for invalid/empty text.
        """
        return {
            'word_count': 0,
            'sentence_count': 0,
            'syllable_count': 0,
            'complex_word_count': 0,
            'char_count': 0,
            'avg_words_per_sentence': 0,
            'avg_syllables_per_word': 0,
            'avg_chars_per_word': 0
        }

    def _count_syllables(self, word: str) -> int:
        """
        Count syllables in a word.
        """
        word = word.lower()
        count = 0
        vowels = "aeiouy"

        if len(word) <= 3:
            return 1

        if word.endswith(('es', 'ed')):
            word = word[:-2]

        prev_char_is_vowel = False
        for char in word:
            is_vowel = char in vowels
            if is_vowel and not prev_char_is_vowel:
                count += 1
            prev_char_is_vowel = is_vowel

        if word.endswith('e'):
            count -= 1

        return max(1, count)

    def calculate_readability_scores(self, metrics: Dict) -> Dict:
        """
        Calculate readability scores with safety checks.
        """
        try:
            # Check for valid metrics
            if (metrics['word_count'] == 0 or
                    metrics['sentence_count'] == 0 or
                    any(metrics[key] < 0 for key in metrics)):
                return {
                    'flesch_reading_ease': None,
                    'flesch_kincaid_grade': None,
                    'gunning_fog': None,
                    'smog_index': None,
                    'automated_readability_index': None
                }

            scores = {}

            # Flesch Reading Ease
            try:
                scores['flesch_reading_ease'] = max(0, min(100,
                                                           206.835 - 1.015 * metrics['avg_words_per_sentence'] -
                                                           84.6 * metrics['avg_syllables_per_word']))
            except:
                scores['flesch_reading_ease'] = None

            # Flesch-Kincaid Grade
            try:
                scores['flesch_kincaid_grade'] = max(0,
                                                     0.39 * metrics['avg_words_per_sentence'] +
                                                     11.8 * metrics['avg_syllables_per_word'] - 15.59)
            except:
                scores['flesch_kincaid_grade'] = None

            # Gunning Fog
            try:
                if metrics['word_count'] > 0:
                    complex_word_percentage = (metrics['complex_word_count'] /
                                               metrics['word_count'] * 100)
                    scores['gunning_fog'] = max(0,
                                                0.4 * (metrics['avg_words_per_sentence'] + complex_word_percentage))
                else:
                    scores['gunning_fog'] = None
            except:
                scores['gunning_fog'] = None

            # SMOG Index
            try:
                if metrics['sentence_count'] >= 30:
                    scores['smog_index'] = 1.0430 * sqrt(metrics['complex_word_count'] *
                                                         (30 / metrics['sentence_count'])) + 3.1291
                else:
                    scores['smog_index'] = None
            except:
                scores['smog_index'] = None

            # Automated Readability Index
            try:
                scores['automated_readability_index'] = max(0,
                                                            4.71 * metrics['avg_chars_per_word'] +
                                                            0.5 * metrics['avg_words_per_sentence'] - 21.43)
            except:
                scores['automated_readability_index'] = None

            return scores
        except Exception as e:
            print(f"Error in calculate_readability_scores: {str(e)}")
            return {
                'flesch_reading_ease': None,
                'flesch_kincaid_grade': None,
                'gunning_fog': None,
                'smog_index': None,
                'automated_readability_index': None
            }

    def get_difficulty_level(self, scores: Dict) -> str:
        """
        Determine difficulty level with safety checks.
        """
        try:
            valid_scores = []
            for score_type in ['flesch_kincaid_grade', 'gunning_fog',
                               'smog_index', 'automated_readability_index']:
                if scores.get(score_type) is not None:
                    valid_scores.append(scores[score_type])

            if not valid_scores:
                return "Unknown"

            avg_grade_level = sum(valid_scores) / len(valid_scores)

            if avg_grade_level < 6:
                return "Elementary"
            elif avg_grade_level < 9:
                return "Middle School"
            elif avg_grade_level < 12:
                return "High School"
            elif avg_grade_level < 16:
                return "College"
            else:
                return "Graduate/Professional"
        except Exception as e:
            print(f"Error in get_difficulty_level: {str(e)}")
            return "Unknown"

    def analyze_article(self, article_data: Dict) -> pd.DataFrame:
        """
        Analyze article with error handling for each section.
        """
        results = []
        try:
            sections_text = self.extract_section_texts(article_data)

            for section_title, texts in sections_text.items():
                try:
                    full_text = ' '.join(text for text in texts if text)
                    if not full_text.strip():
                        continue

                    metrics = self.calculate_text_metrics(full_text)
                    if metrics['word_count'] == 0:
                        continue

                    readability_scores = self.calculate_readability_scores(metrics)
                    difficulty_level = self.get_difficulty_level(readability_scores)

                    # Calculate average grade level
                    valid_scores = [
                        score for score in [
                            readability_scores['flesch_kincaid_grade'],
                            readability_scores['gunning_fog'],
                            readability_scores['smog_index'],
                            readability_scores['automated_readability_index']
                        ] if score is not None
                    ]

                    avg_grade_level = (sum(valid_scores) / len(valid_scores)
                                       if valid_scores else None)

                    result = {
                        'title': article_data['title'],
                        'category': article_data['category'],
                        'section': section_title,
                        'difficulty_level': difficulty_level,
                        'avg_grade_level': avg_grade_level,
                        **metrics,
                        **readability_scores
                    }
                    results.append(result)
                except Exception as e:
                    print(f"Error processing section {section_title}: {str(e)}")
                    continue

        except Exception as e:
            print(f"Error processing article sections: {str(e)}")

        if not results:
            print(f"No valid sections found for article {article_data.get('title', 'Unknown')}")
            return pd.DataFrame()

        return pd.DataFrame(results)

    def generate_readability_report(self, df: pd.DataFrame) -> str:
        """
        Generate a human-readable report from the analysis results.
        """
        report = []
        report.append("=== Wikipedia Articles Readability Analysis ===\n")

        # Overall statistics
        report.append("Overall Statistics:")
        report.append(f"Total articles analyzed: {df['title'].nunique()}")
        report.append(f"Total sections analyzed: {len(df)}")

        # Difficulty level distribution
        difficulty_dist = df['difficulty_level'].value_counts()
        report.append("\nDifficulty Level Distribution:")
        for level, count in difficulty_dist.items():
            report.append(f"{level}: {count} sections ({count / len(df) * 100:.1f}%)")

        # Article-level analysis
        report.append("\nArticle-by-Article Analysis:")
        for title in df['title'].unique():
            article_df = df[df['title'] == title]
            report.append(f"\n{title}:")
            report.append(f"Category: {article_df['category'].iloc[0]}")
            report.append(f"Average difficulty: {article_df['difficulty_level'].mode().iloc[0]}")
            report.append("Sections:")
            for _, row in article_df.iterrows():
                report.append(f"  - {row['section']}")
                report.append(f"    Difficulty: {row['difficulty_level']}")
                report.append(f"    Grade Level: {row['avg_grade_level']:.1f}")
                report.append(f"    Words: {row['word_count']}")

        return "\n".join(report)

    def analyze_json_file(self, json_file_path: Union[str, Path],
                          output_file: Union[str, Path, None] = None,
                          report_file: Union[str, Path, None] = None) -> pd.DataFrame:
        """
        Analyze articles and generate both detailed data and readable report.
        """
        data = self.load_wiki_json(json_file_path)
        all_results = []

        for title, article_data in tqdm(data['articles'].items(), desc="Analyzing articles"):
            try:
                article_df = self.analyze_article(article_data)
                all_results.append(article_df)
            except Exception as e:
                print(f"Error processing article {title}: {str(e)}")
                continue

        if not all_results:
            raise ValueError("No articles were successfully processed")

        final_df = pd.concat(all_results, ignore_index=True)

        # Generate and save report
        report = self.generate_readability_report(final_df)
        if report_file:
            try:
                with open(report_file, 'w', encoding='utf-8') as f:
                    f.write(report)
            except Exception as e:
                print(f"Error saving report: {str(e)}")

        # Save detailed data
        if output_file:
            try:
                if str(output_file).endswith('.csv'):
                    final_df.to_csv(output_file, index=False)
                elif str(output_file).endswith('.json'):
                    final_df.to_json(output_file, orient='records', indent=2)
                elif str(output_file).endswith('.xlsx'):
                    final_df.to_excel(output_file, index=False)
            except Exception as e:
                print(f"Error saving output file: {str(e)}")

        return final_df, report
# Example usage
if __name__ == "__main__":

    try:
        calculator = WikiSectionReadabilityCalculator()

        results_df, report = calculator.analyze_json_file(
            "/Users/mollyhan/PycharmProjects/Cognitext/data/text_sample.json",
        "/Users/mollyhan/PycharmProjects/Cognitext/data/readability_analysis.csv",
            "/Users/mollyhan/PycharmProjects/Cognitext/data/readability_report.txt"
        )

        print("\nAnalysis completed successfully!")
        print("\nReport Preview:")
        print(report[:1000] + "..." if len(report) > 1000 else report)

    except Exception as e:
        print(f"Error: {str(e)}")